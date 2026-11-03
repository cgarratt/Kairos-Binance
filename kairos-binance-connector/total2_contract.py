"""Exact TradingView TOTAL2 indicator contract, shared with the MCP bridge."""
import math
from datetime import datetime, timezone, timedelta

def expected_close(interval, now=None):
    now = now or datetime.now(timezone.utc)
    day = now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return day if interval == '1d' else day-timedelta(days=day.weekday())

def validate_total2(data, interval, now=None):
    if interval not in ('1d','1w') or not isinstance(data, dict):
        raise ValueError('Invalid interval/payload')
    if (data.get('schema') != 'kairos.total2.v1' or data.get('symbol') != 'CRYPTOCAP:TOTAL2'
        or data.get('source') != 'TradingView CRYPTOCAP:TOTAL2' or data.get('interval') != interval
        or data.get('closed_only') is not True or data.get('parameters') != [14,14,14,3,3]):
        raise ValueError('Invalid TOTAL2 identity, parameters or open candle')
    closing = datetime.fromisoformat(data['close_utc'].replace('Z','+00:00'))
    opening = datetime.fromisoformat(data['open_utc'].replace('Z','+00:00'))
    if (closing.utcoffset() != timedelta(0) or opening.utcoffset() != timedelta(0)
        or closing != expected_close(interval,now)
        or closing-opening != timedelta(days=1 if interval=='1d' else 7)):
        raise ValueError('TOTAL2 stale, future or unaligned candle')
    values = {k:data[k] for k in ('rsi','ma','k','d')}
    if any(type(v) not in (float,int) or not math.isfinite(v) or not 0<=v<=100 for v in values.values()):
        raise ValueError('Invalid TOTAL2 oscillator')
    return dict(**values, symbol='TOTAL2', interval=interval, status='OK',
                source=data['source'], close_utc=closing.isoformat(),
                close_lima=closing.astimezone(timezone(timedelta(hours=-5))).strftime('%d/%m/%Y %H:%M Lima'),
                received_utc=data.get('received_utc'),reason='')
