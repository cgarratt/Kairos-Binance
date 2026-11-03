"""TradingView webhook -> validated read-only MCP snapshots. No exchange access."""
from contextlib import contextmanager
import hmac
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from total2_contract import validate_total2

@contextmanager
def _connect():
    path=Path(os.getenv('KAIROS_TOTAL2_DB','/tmp/kairos-total2.sqlite3'))
    db=sqlite3.connect(path,timeout=1)
    db.execute('CREATE TABLE IF NOT EXISTS snapshots (interval TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    try:
        with db:
            yield db
    finally:
        db.close()

def receive(data, now=None):
    secret=os.getenv('KAIROS_TOTAL2_WEBHOOK_SECRET','')
    if len(secret)<32:
        return {'status':'NOT_CONFIGURED'},503
    if not isinstance(data,dict) or not isinstance(data.get('token'),str) or not hmac.compare_digest(data['token'],secret):
        return {'status':'UNAUTHORIZED'},401
    clean={k:v for k,v in data.items() if k!='token'}
    interval=clean.get('interval')
    try:
        validated=validate_total2(clean,interval,now)
    except (ValueError,KeyError,TypeError,AttributeError):
        return {'status':'DATA_ERROR','reason':'Invalid identity, parameters, values or UTC closed candle'},400
    clean={k:clean[k] for k in ('schema','symbol','source','interval','closed_only','parameters','open_utc','close_utc','rsi','ma','k','d')}
    clean['close_utc']=validated['close_utc']
    clean['open_utc']=datetime.fromisoformat(clean['open_utc'].replace('Z','+00:00')).isoformat()
    clean['received_utc']=(now or datetime.now(timezone.utc)).isoformat()
    try:
        with _connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT payload FROM snapshots WHERE interval=?',(interval,)).fetchone()
            if row:
                previous=json.loads(row[0])
                if previous['close_utc']==clean['close_utc']:
                    if any(previous[k]!=clean[k] for k in ('rsi','ma','k','d')):
                        return {'status':'CONFLICT'},409
                    return {'status':'OK','duplicate':True},200
            db.execute('INSERT OR REPLACE INTO snapshots VALUES (?,?)',(interval,json.dumps(clean,allow_nan=False)))
    except (OSError,sqlite3.Error):
        return {'status':'STORAGE_ERROR'},503
    return {'status':'OK','interval':interval,'close_utc':clean['close_utc']},200

def context(now=None):
    records={}
    try:
        with _connect() as db:
            for interval,payload in db.execute('SELECT interval,payload FROM snapshots'):
                try:
                    data=json.loads(payload)
                    validate_total2(data,interval,now)
                    records[interval]=data
                except (ValueError,KeyError,TypeError):
                    pass
    except (OSError,sqlite3.Error):
        return {'status':'DATA_ERROR','source':'TradingView CRYPTOCAP:TOTAL2','records':{},'reason':'TOTAL2 storage unavailable'}
    return {'status':'OK' if records else 'PENDING_DATA','source':'TradingView CRYPTOCAP:TOTAL2',
            'records':records,'reason':'' if records else 'No current confirmed TOTAL2 webhook received',
            'read_only':True,'provenance':'Configured TradingView webhook; not a direct TradingView API pull'}
