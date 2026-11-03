import copy
import os
from datetime import datetime,timezone,timedelta
import pytest
from total2_bridge import receive,context
from total2_contract import expected_close

NOW=datetime(2026,11,3,12,tzinfo=timezone.utc)

@pytest.fixture(autouse=True)
def storage(tmp_path,monkeypatch):
    monkeypatch.setenv('KAIROS_TOTAL2_DB',str(tmp_path/'total2.sqlite'))
    monkeypatch.setenv('KAIROS_TOTAL2_WEBHOOK_SECRET','a'*64)

def payload(interval='1d'):
    end=expected_close(interval,NOW)
    return dict(token='a'*64,schema='kairos.total2.v1',symbol='CRYPTOCAP:TOTAL2',
                source='TradingView CRYPTOCAP:TOTAL2',interval=interval,closed_only=True,
                parameters=[14,14,14,3,3],open_utc=(end-timedelta(days=1 if interval=='1d' else 7)).isoformat(),
                close_utc=end.isoformat(),rsi=28.,ma=26.,k=19.,d=14.)

def test_authenticated_roundtrip_both_timeframes():
    for interval in ['1d','1w']:
        data=payload(interval)
        assert receive(data,NOW)[1]==200
        assert receive(data,NOW)[0]['duplicate']
    out=context(NOW)
    assert out['status']=='OK' and set(out['records'])=={'1d','1w'}
    assert 'token' not in str(out)

def test_secret_and_configuration(monkeypatch):
    data=payload();data['token']='bad'
    assert receive(data,NOW)[1]==401
    monkeypatch.delenv('KAIROS_TOTAL2_WEBHOOK_SECRET')
    assert receive(payload(),NOW)[1]==503

@pytest.mark.parametrize('key,value',[('closed_only',False),('symbol','BTCUSDT'),('interval','4h'),('rsi',101),('parameters',[14,14,14,1,1]),('rsi',float('nan'))])
def test_invalid_rejected(key,value):
    data=payload();data[key]=value
    assert receive(data,NOW)[1]==400
    assert context(NOW)['status']=='PENDING_DATA'

def test_conflicting_duplicates_no_overwrite():
    data=payload();assert receive(data,NOW)[1]==200
    data['rsi']=27.;data['close_utc']=data['close_utc'].replace('+00:00','Z')
    assert receive(data,NOW)[1]==409
    assert context(NOW)['records']['1d']['rsi']==28.

def test_stale_rollover_is_not_current():
    assert receive(payload(),NOW)[1]==200
    out=context(NOW+timedelta(days=1))
    assert out['status']=='PENDING_DATA'

def test_http_route_is_registered_and_rejects_unauthenticated():
    from server import mcp
    from starlette.testclient import TestClient
    with TestClient(mcp.http_app()) as client:
        data=payload();data['token']='bad'
        assert client.post('/total2/webhook',json=data).status_code==401
        assert client.post('/total2/webhook',content='x'*9000).status_code==413
