"""One explicit dashboard load; closed history is cached at the HTTP gate.
No background refresh, scheduler, account access, or order submission.
"""
import copy
import threading
import time
from decimal import Decimal
from market_data import SYMBOLS
from market_intelligence import spot_prices, _klines, indicator_series
from binance_http import DataError, RateLimitError
from cycle_phase import cycle_phase

_LOCK = threading.Lock()
_CACHE = None

def dashboard_snapshot():
    global _CACHE
    # Concurrent manual clicks join the same completed observation.
    with _LOCK:
        if _CACHE and time.monotonic()-_CACHE[0]<60:
            return copy.deepcopy(_CACHE[1])
        prices=spot_prices()
        if prices.get('status')!='OK':return prices
        histories={}; indicators={}; cycles={}
        try:
            for symbol in SYMBOLS:
                for interval,limit in (('1d',999),):
                    key=symbol+':'+interval
                    try:
                        candles=_klines(symbol,interval,limit,allow_short=True)
                        if not candles:raise DataError('No closed candles')
                        histories[key]={'status':'OK','source':'Binance Spot','symbol':symbol,
                            'interval':interval,'closed_only':True,'count':len(candles),'records':candles}
                        if interval=='1d':
                            daily=[dict(b,high=Decimal(b['high']),low=Decimal(b['low']),close=Decimal(b['close'])) for b in candles]
                            cycles[symbol]=cycle_phase(symbol,_daily=daily)
                        if interval=='1d':
                            series=indicator_series([float(b['close']) for b in candles])
                            values={name:round(seq[-1],10) if seq[-1] is not None else None for name,seq in series.items()}
                            indicators[key]={'status':'OK' if all(v is not None for v in values.values()) else 'DATA_ERROR',
                                'source':'Binance Spot','symbol':symbol,'interval':interval,'closed_only':True,
                                'close_utc':candles[-1]['close_utc'],'last_close':candles[-1]['close'],
                                'history_candles':len(candles),'values':values}
                    except RateLimitError:raise
                    except (DataError,ValueError,TypeError,KeyError) as exc:
                        histories[key]={'status':'DATA_ERROR','source':'Binance Spot','symbol':symbol,
                            'interval':interval,'reason':str(exc),'records':[]}
        except RateLimitError as exc:
            return {'status':'DATA_ERROR','source':'Binance Spot','http_status':exc.http_status,
                'retry_at_utc':exc.retry_at_utc,'retry_after_seconds':exc.retry_after_seconds,'reason':str(exc)}
        result={'status':'OK','source':'Binance Spot','spot':prices,'histories':histories,
            'indicators':indicators,'cycles':cycles,'as_observed_utc':prices['as_observed_utc'],
            'policy':'MANUAL_SNAPSHOT','atomic':False}
        _CACHE=(time.monotonic(),copy.deepcopy(result))
        return result
