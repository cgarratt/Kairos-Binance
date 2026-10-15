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

def macro_fibo(symbol='BTCUSDT', start_date=None, end_date=None, swing_low_date=None):
    """Return EXPLORATORY anchors and descending retracement levels, not approved O2 orders.

    Swing-low auto candidate = lowest daily LOW before the observed peak (not a certified cycle low).
    A manual YYYY-MM-DD low anchor may be provided for verification. No automatic cycle identification.
    """
    try:
        candles,pages=fetch_history(symbol,start_date,end_date)
        if len(candles)<60: raise DataError('Need >=60 closed daily candles for macro observation')
        peak=max(candles,key=lambda c:c['high'])
        preceding=[c for c in candles if c['open_ms']<peak['open_ms']]
        if not preceding: raise DataError('Historical peak occurs at start of coverage; no preceding swing low')
        auto_low=min(preceding,key=lambda c:c['low'])
        if swing_low_date:
            t=_day_ms(swing_low_date)
            matching=[c for c in preceding if c['open_ms']==t]
            if not matching: raise DataError('Specified swing_low_date missing or not before the peak')
            low=matching[0];method='user_selected_daily_low'
        else:
            low=auto_low;method='lowest_daily_low_preceding_observed_peak_UNVERIFIED'
        high=peak['high']; bottom=low['low']
        if high<=bottom: raise DataError('Degenerate Fibonacci anchors')
        fib={x:format(high-(high-bottom)*Decimal(x),'f') for x in LEVELS}
        return {'status':'OK','source':'Binance Spot /api/v3/klines','symbol':symbol,
                'candle_interval':'1d','closed_only':True,'scope':'EXPLORATORY_ONLY',
                'approval_status':'REQUIRES_HUMAN_CONFIRMATION',
                'note':'Observed ATH is Binance-listed daily-high maximum, NOT necessarily global all-exchange ATH. Auto low is NOT a certified final-bear-cycle swing low.',
                'coverage':{'first_open_utc':_iso(candles[0]['open_ms']),
                            'last_close_utc':_iso(candles[-1]['open_ms']+DAY),
                            'days':len(candles),'pages':pages,'requested_start_date':start_date,
                            'requested_end_date':end_date},
                'observed_ath':{'price':format(high,'f'),'date_utc':_iso(peak['open_ms'])},
                'swing_low_candidate':{'price':format(bottom,'f'),'date_utc':_iso(low['open_ms']),'method':method},
                'drawdown_range_pct':round(float((high-bottom)/high*100),4),
                'retracement_from_high':fib,
                'warning':'Do NOT change approved Fibo Macro, O2-O5 or limit orders without comparison to certified TradingView anchors and explicit user approval.'}
    except (DataError, ValueError, TypeError, ArithmeticError, KeyError) as e:
        return {'status':'DATA_ERROR','source':'Binance Spot','symbol':symbol,'reason':str(e),
                'approval_status':'NOT_APPROVED'}
