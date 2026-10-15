"""Kairos macro Fibonacci candidate anchors from paginated Binance Spot DAILY candles.
Read-only; NEVER promotes candidates to approved portfolio/order anchors.
"""
from __future__ import annotations
import datetime as dt
import math
from decimal import Decimal
from market_data import SYMBOLS, DataError
from market_intelligence import _request

DAY = 86_400_000
LEVELS = ('0.236', '0.382', '0.5', '0.618', '0.786')
DEFAULT_CYCLE_START_DATE = '2023-01-01'  # Provisional last bull-market window; user-adjustable
MAX_PAGES = 16  # 16,000 daily candles (>43y); bounded per call

def _iso(ms):
    return dt.datetime.fromtimestamp(ms/1000,dt.timezone.utc).isoformat()

def _day_ms(value):
    try:
        parsed = dt.date.fromisoformat(value)
    except (TypeError, ValueError) as e:
        raise DataError('Dates must use YYYY-MM-DD') from e
    return int(dt.datetime.combine(parsed,dt.time(),tzinfo=dt.timezone.utc).timestamp()*1000)

def fetch_history(symbol, start_date=None, end_date=None, now=None):
    """Fetch from listed candle forward; optionally constrain dates. Reject gaps and truncation."""
    if symbol not in SYMBOLS: raise DataError('Unsupported Kairos symbol')
    now = now or dt.datetime.now(dt.timezone.utc)
    last_closed = int(now.timestamp()*1000)//DAY*DAY  # exclusive last completed day
    start = _day_ms(start_date) if start_date else 0
    end = min(_day_ms(end_date)+DAY if end_date else last_closed, last_closed)
    if start>=end: raise DataError('Invalid or not-yet-closed historical date range')
    out=[]; cursor=start; pages=0
    while cursor<end:
        if pages>=MAX_PAGES: raise DataError('History exceeds page safety limit; narrow date range')
        raw=_request('/api/v3/klines', {'symbol':symbol,'interval':'1d', 'startTime':cursor,
                                        'endTime':end-1, 'limit':1000})
        pages+=1
        if not isinstance(raw,list): raise DataError('Malformed Binance history payload')
        if not raw: break
        prior=None
        for candle in raw:
            if not isinstance(candle,list) or len(candle)<7: raise DataError('Malformed daily candle')
            try:
                t=int(candle[0]); hi=Decimal(str(candle[2])); lo=Decimal(str(candle[3]))
                close_ms=int(candle[6])
            except (ValueError, TypeError, ArithmeticError, IndexError) as exc:
                raise DataError(f'Malformed daily candle fields at page {pages}') from exc
            # Binance legacy Spot history can contain candles whose closeTime metadata
            # differs slightly from the canonical end-of-day millisecond. Anchor the
            # session on UTC-aligned openTime; reject cross-session close times.
            if t % DAY:
                raise DataError(f'Non-UTC daily open at {_iso(t)}')
            if not t <= close_ms < t + DAY:
                raise DataError(f'Cross-day daily close metadata at {_iso(t)}: {close_ms}')
            if not (lo.is_finite() and hi.is_finite() and 0 < lo <= hi):
                raise DataError(f'Invalid daily high/low at {_iso(t)}: {hi}/{lo}')
            high, low = hi, lo
            if prior is not None and t!=prior+DAY: raise DataError('Gap or duplicate in historical candles')
            if t<cursor or t>=end or t+DAY>last_closed: raise DataError('Out-of-range or unclosed daily candle')
            out.append({'open_ms':t,'high':high,'low':low})
            prior=t
        new_cursor=out[-1]['open_ms']+DAY
        if new_cursor<=cursor: raise DataError('Non-progressing Binance pagination')
        cursor=new_cursor
        if len(raw)<1000: break
    if not out: raise DataError('No historical candles for selected date range')
    if any(b['open_ms']!=a['open_ms']+DAY for a,b in zip(out,out[1:])):
        raise DataError('Gap between paginated history batches')
    # If history started after requested date, Binance may have begun listing later: report actual coverage.
    # An empty gap after first observation is not a valid complete date range.
    if out[-1]['open_ms']+DAY<end: raise DataError('Missing trailing Binance historical candles')
    return out, pages

def macro_fibo(symbol='BTCUSDT', start_date=None, end_date=None, swing_low_date=None, cycle_start_date=DEFAULT_CYCLE_START_DATE):
    """Separate ATH/ATL over history from peak/low of selected recent cycle.

    Cycle high is max daily high on/after cycle_start_date (2023-01-01 by default).
    Cycle low is strictly AFTER cycle high and provisional. Explicit swing_low_date
    selects a daily candle after the CYCLE HIGH, never the historical ATH.
    """
    try:
        candles, pages = fetch_history(symbol, start_date, end_date)
        if len(candles) < 60:
            raise DataError('Need >=60 closed daily candles for macro observation')
        peak = max(candles, key=lambda c: c['high'])
        atl = min(candles, key=lambda c: c['low'])
        cycle_start_ms = _day_ms(cycle_start_date)
        cycle_candles = [c for c in candles if c['open_ms'] >= cycle_start_ms]
        if len(cycle_candles) < 2:
            raise DataError('Insufficient closed daily candles after cycle_start_date')
        cycle_peak = max(cycle_candles, key=lambda c: c['high'])
        subsequent = [c for c in cycle_candles if c['open_ms'] > cycle_peak['open_ms']]
        base = {
            'status':'OK', 'source':'Binance Spot /api/v3/klines',
            'symbol':symbol, 'candle_interval':'1d', 'closed_only':True,
            'scope':'EXPLORATORY_ONLY', 'approval_status':'REQUIRES_HUMAN_CONFIRMATION',
            'coverage': {'first_open_utc':_iso(candles[0]['open_ms']),
                'last_close_utc':_iso(candles[-1]['open_ms']+DAY),
                'days':len(candles), 'pages':pages,
                'requested_start_date':start_date, 'requested_end_date':end_date},
            'observed_ath':{'price':format(peak['high'],'f'),'date_utc':_iso(peak['open_ms'])},
            'observed_atl':{'price':format(atl['low'],'f'),'date_utc':_iso(atl['open_ms']),
                'scope':'observed_Binance_history_NOT_all_exchanges'},
            'cycle_start_date':cycle_start_date,
            'cycle_peak':{'price':format(cycle_peak['high'],'f'), 'date_utc':_iso(cycle_peak['open_ms']),
                'method':'highest_daily_high_on_or_after_cycle_start_date_UNVERIFIED'},
            'cycle_rule':'highest daily high within selected bull-cycle window; then lowest daily low STRICTLY AFTER cycle peak',
            'warning':'The post-cycle-high low is provisional, not a certified completed bear-cycle low. Never update O2-O5, approved anchors or orders without explicit user approval.'
        }
        if not subsequent:
            base.update({'cycle_status':'NO_POST_CYCLE_PEAK_CANDLES',
                         'swing_low_post_cycle_peak':None, 'swing_low_post_ath':None,
                         'retracement_from_high':None,
                         'note':'Cycle peak is on the last closed daily candle; a subsequent low does not yet exist.'})
            return base
        if swing_low_date:
            t=_day_ms(swing_low_date)
            matches=[c for c in subsequent if c['open_ms']==t]
            if not matches:
                raise DataError('Specified swing_low_date must be present strictly AFTER selected cycle peak')
            low=matches[0]
            method='user_selected_post_cycle_peak_daily_low_UNVERIFIED'
        else:
            low=min(subsequent,key=lambda c:c['low'])
            method='lowest_post_cycle_peak_daily_low_PROVISIONAL'
        top=cycle_peak['high']; bottom=low['low']
        if top<=bottom: raise DataError('Degenerate cycle Fibonacci anchors')
        base.update({'cycle_status':'POST_CYCLE_PEAK_DRAWDOWN_IN_PROGRESS_OR_UNCONFIRMED',
                     'swing_low_post_cycle_peak':{'price':format(bottom,'f'),
                         'date_utc':_iso(low['open_ms']), 'method':method,
                         'certified_cycle_low':False},
                     'drawdown_range_pct':round(float((top-bottom)/top*100),4),
                     'retracement_from_high':{x:format(top-(top-bottom)*Decimal(x),'f') for x in LEVELS},
                     'note':'Descending levels use recent cycle peak (not necessarily all-time ATH) and post-peak low; exploratory, NOT approved Kairos levels.'})
        base['swing_low_post_ath'] = None if base.get('swing_low_post_cycle_peak') is None else dict(base['swing_low_post_cycle_peak'], legacy_field_note='Deprecated: post CYCLE high, not necessarily historical ATH')
        return base
    except (DataError, ValueError, TypeError, ArithmeticError, KeyError) as e:
        return {'status':'DATA_ERROR','source':'Binance Spot','symbol':symbol,
                'reason':str(e),'approval_status':'NOT_APPROVED'}
