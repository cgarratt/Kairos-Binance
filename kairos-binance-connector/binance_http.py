"""One read-only HTTP gate for Binance; no retries or alternate-host bypass."""
import contextvars
import functools
import hashlib
import datetime as dt
import email.utils
import json
import logging
import os
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://data-api.binance.vision'
_LOCK = threading.Lock()
_LAST = 0.
_TOOL = contextvars.ContextVar('kairos_tool', default='direct')
_LOG = logging.getLogger('kairos.binance')
_LOG.setLevel(logging.INFO)
if not _LOG.handlers:
    _LOG.addHandler(logging.StreamHandler())
_LOG.propagate=False
STATE_PATH = os.environ.get('BINANCE_GUARD_DB', '/tmp/kairos-binance-guard.sqlite3')

class DataError(RuntimeError):
    pass

class RateLimitError(DataError):
    def __init__(self, status, until):
        self.http_status = status
        self.retry_at_utc = dt.datetime.fromtimestamp(until, dt.timezone.utc).isoformat()
        self.retry_after_seconds = max(0, int(until-time.time())+1)
        super().__init__(f'Binance HTTP {status}; requests paused until {self.retry_at_utc}')

def _state(until=None, status=None):
    # Persistent across process restarts when the same filesystem survives.
    with sqlite3.connect(STATE_PATH, timeout=2) as db:
        db.execute('CREATE TABLE IF NOT EXISTS cooldown (id INTEGER PRIMARY KEY, until REAL, status INTEGER)')
        if until is not None:
            db.execute('INSERT INTO cooldown VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET until=max(cooldown.until,excluded.until),status=excluded.status', (until,status))
        return db.execute('SELECT until,status FROM cooldown WHERE id=1').fetchone()

def _deadline(exc, body, now):
    deadlines=[]
    retry=exc.headers.get('Retry-After') if exc.headers else None
    if retry:
        try:deadlines.append(now+max(0,float(retry)))
        except ValueError:
            try:deadlines.append(email.utils.parsedate_to_datetime(retry).timestamp())
            except (ValueError,TypeError,OverflowError):pass
    match=re.search(r'banned until\s+(\d{10,16})',body,re.I)
    if match:
        stamp=int(match[1]);deadlines.append(stamp/1000 if stamp>100000000000 else stamp)
    # Unknown expiry: conservative local pause, not a claimed Binance expiry.
    return max([now+1]+deadlines) if deadlines else now+(900 if exc.code==418 else 60)

def audited_tool(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        token=_TOOL.set(func.__name__)
        try:return func(*args, **kwargs)
        finally:_TOOL.reset(token)
    return wrapped

def _cache_spec(path, params, now):
    if path!='/api/v3/klines':return None
    periods={'15m':900,'1h':3600,'4h':14400,'1d':86400}
    period=periods.get(params.get('interval'))
    if not period:return None
    boundary=int(now//period)*period
    end=params.get('endTime')
    immutable=end is not None and float(end)<boundary*1000
    # A forming candle may be in raw Binance payload, but consumers exclude it.
    # Such a response MUST expire before that candle closes.
    expires=now+86400*30 if immutable else boundary+period
    key=hashlib.sha256(json.dumps([path,params,None if immutable else boundary],sort_keys=True).encode()).hexdigest()
    return key,expires

def _history_cache(spec, payload=None):
    if not spec:return None
    key,expires=spec
    with sqlite3.connect(STATE_PATH,timeout=2) as db:
        db.execute('CREATE TABLE IF NOT EXISTS history (key TEXT PRIMARY KEY, expires REAL, payload TEXT)')
        if payload is not None:
            db.execute('DELETE FROM history WHERE expires<=?',(time.time(),))
            db.execute('INSERT OR REPLACE INTO history VALUES(?,?,?)',(key,expires,json.dumps(payload)))
            db.execute('DELETE FROM history WHERE key NOT IN (SELECT key FROM history ORDER BY rowid DESC LIMIT 256)')
        row=db.execute('SELECT payload FROM history WHERE key=? AND expires>?',(key,time.time())).fetchone()
        return json.loads(row[0]) if row else None

def _audit(path,params,status,headers=None,cache='MISS',started=None):
    headers=headers or {}
    weights={k:str(v) for k,v in headers.items() if str(k).lower().startswith('x-mbx-used-weight')}
    _LOG.info('binance_request %s',json.dumps({'tool':_TOOL.get(),'path':path,
        'symbol':params.get('symbol'),'interval':params.get('interval'),
        'limit':params.get('limit'),'http_status':status if isinstance(status,(int,type(None))) else 200,'used_weight':weights,
        'retry_after':headers.get('Retry-After'),'cache':cache,
        'duration_ms':round((time.monotonic()-started)*1000) if started else 0}))

def request_json(path, params):
    global _LAST
    if not _LOCK.acquire(timeout=2):raise DataError('Binance request queue busy; retry later')
    try:
        spec=_cache_spec(path,params,time.time())
        cached=_history_cache(spec)
        if cached is not None:
            _audit(path,params,None,cache='HIT');return cached
        current=_state()
        if current and current[0]>time.time():
            _audit(path,params,current[1],cache='BLOCKED_LOCAL')
            raise RateLimitError(current[1],current[0])
        time.sleep(max(0,.3-(time.monotonic()-_LAST)))
        req=urllib.request.Request(BASE+path+'?'+urllib.parse.urlencode(params),headers={'User-Agent':'KairosMarketData/5.3.3'})
        try:
            _LAST=time.monotonic()
            with urllib.request.urlopen(req,timeout=12) as response:
                result=json.load(response)
                _audit(path,params,getattr(response,'status',200),getattr(response,'headers',{}),started=_LAST)
            if isinstance(result,list):_history_cache(spec,result)
            return result
        except urllib.error.HTTPError as exc:
            _audit(path,params,exc.code,exc.headers,started=_LAST)
            if exc.code in (418,429):
                body=exc.read(8192).decode('utf-8',errors='replace')
                until=_deadline(exc,body,time.time());_state(until,exc.code)
                logging.getLogger(__name__).warning("Binance cooldown http=%s retry_at_utc=%s",exc.code,dt.datetime.fromtimestamp(until,dt.timezone.utc).isoformat())
                raise RateLimitError(exc.code,until) from exc
            raise DataError(f'Binance HTTP {exc.code} on {path}') from exc
        except (OSError,ValueError) as exc:
            _audit(path,params,None,cache="NETWORK_ERROR",started=_LAST)
            raise DataError(f'Binance request failed on {path}: {type(exc).__name__}') from exc
    finally:_LOCK.release()
