"""One read-only HTTP gate for Binance; no retries or alternate-host bypass."""
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

def request_json(path, params):
    global _LAST
    if not _LOCK.acquire(timeout=2):raise DataError('Binance request queue busy; retry later')
    try:
        current=_state()
        if current and current[0]>time.time():raise RateLimitError(current[1],current[0])
        time.sleep(max(0,.3-(time.monotonic()-_LAST)))
        req=urllib.request.Request(BASE+path+'?'+urllib.parse.urlencode(params),headers={'User-Agent':'KairosMarketData/5.3.2'})
        try:
            _LAST=time.monotonic()
            with urllib.request.urlopen(req,timeout=12) as response:return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in (418,429):
                body=exc.read(8192).decode('utf-8',errors='replace')
                until=_deadline(exc,body,time.time());_state(until,exc.code)
                logging.getLogger(__name__).warning("Binance cooldown http=%s retry_at_utc=%s",exc.code,dt.datetime.fromtimestamp(until,dt.timezone.utc).isoformat())
                raise RateLimitError(exc.code,until) from exc
            raise DataError(f'Binance HTTP {exc.code} on {path}') from exc
        except (OSError,ValueError) as exc:
            raise DataError(f'Binance request failed on {path}: {type(exc).__name__}') from exc
    finally:_LOCK.release()
