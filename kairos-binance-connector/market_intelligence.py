"""Public Binance Spot market intelligence, read-only, fail-closed."""
from __future__ import annotations
import datetime as dt
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from market_data import BASE, SYMBOLS, DataError

INTERVALS = {'15m':900000, '1h':3600000, '4h':14400000, '1d':86400000}


def _request(path, params):
    url = BASE + path + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent':'KairosMarketIntelligence/5.1'})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.load(resp)
    except (ValueError, OSError, urllib.error.HTTPError) as exc:
        raise DataError(f'Binance Spot request failed ({path}): {exc}') from exc


def _symbols(symbols):
    if symbols is None:
        return list(SYMBOLS)
    if isinstance(symbols, str):
        symbols = [symbols]
    if not isinstance(symbols, (list, tuple)) or not symbols or len(set(symbols)) != len(symbols) or any(s not in SYMBOLS for s in symbols):
        raise DataError('Symbols must be a nonempty unique subset of the 12 Kairos Spot pairs')
    return list(symbols)


def _finite(s):
    try:
        x = float(s)
    except (ValueError, TypeError, OverflowError):
        raise DataError('Non-numeric Binance market value')
    if not math.isfinite(x):
        raise DataError('Non-finite Binance market value')
    return x


def _utc(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).isoformat()


def spot_prices(symbols=None):
    try:
        selected = _symbols(symbols)
        # two independently sampled public endpoints; price is ticker price, not executable quote
        prices = _request('/api/v3/ticker/price', {'symbols':json.dumps(selected,separators=(',',':'))})
        books = _request('/api/v3/ticker/bookTicker', {'symbols':json.dumps(selected,separators=(',',':'))})
        observed = dt.datetime.now(dt.timezone.utc).isoformat()
        p = {v['symbol']:v for v in prices}; b = {v['symbol']:v for v in books}
        out = []
        for s in selected:
            if s not in p or s not in b:
                raise DataError(f'Missing price or top-of-book for {s}')
            px = _finite(p[s]['price']); bid = _finite(b[s]['bidPrice']); ask = _finite(b[s]['askPrice'])
            if px <= 0 or bid <= 0 or ask <= 0 or bid > ask:
                raise DataError(f'Invalid market quote for {s}')
            out.append({'symbol':s, 'price':str(p[s]['price']), 'best_bid':str(b[s]['bidPrice']),
                        'best_ask':str(b[s]['askPrice']), 'spread_pct':round((ask-bid)/((bid+ask)/2)*100,6),
                        'bid_qty':str(b[s]['bidQty']), 'ask_qty':str(b[s]['askQty'])})
        return {'status':'OK','source':'Binance Spot','as_observed_utc':observed,
                'note':'Non-atomic REST reads; observation timestamp is local fetch time, not exchange trade timestamp', 'records':out}
    except (DataError, KeyError, IndexError, TypeError) as e:
        return {'status':'DATA_ERROR','source':'Binance Spot','reason':str(e),'records':[]}


def _klines(symbol, interval, limit, now=None):
    if symbol not in SYMBOLS: raise DataError('Unsupported symbol')
    if interval not in INTERVALS: raise DataError('Unsupported interval')
    if not isinstance(limit,int) or not 1 <= limit <= 999: raise DataError('Invalid candle limit (1..999)')
    now_ms=int((now or dt.datetime.now(dt.timezone.utc)).timestamp()*1000)
    period=INTERVALS[interval]
    payload=_request('/api/v3/klines', {'symbol':symbol,'interval':interval,'limit':limit+1})
    if not isinstance(payload,list): raise DataError('Unexpected kline payload')
    candles=[]
    for k in payload:
        if not isinstance(k,list) or len(k)<11: raise DataError('Malformed kline')
        start=int(k[0]); close_exclusive=start+period
        if start%period or int(k[6]) != close_exclusive-1:
            raise DataError('Misaligned or inconsistent kline timestamps')
        if close_exclusive>now_ms: continue
        op,hi,lo,cl,vol = [_finite(v) for v in k[1:6]]
        if min(op,hi,lo,cl)<=0 or vol<0 or hi<max(op,cl) or lo>min(op,cl) or hi<lo:
            raise DataError('Invalid OHLCV')
        candles.append({'open_ms':start,'close_exclusive_ms':close_exclusive,'open_utc':_utc(start),
                        'close_utc':_utc(close_exclusive),'open':str(k[1]),'high':str(k[2]),
                        'low':str(k[3]),'close':str(k[4]),'volume_base':str(k[5]),
                        'volume_quote':str(k[7]),'trades':int(k[8])})
    candles=sorted(candles,key=lambda c:c['open_ms'])
    if len({c['open_ms'] for c in candles}) != len(candles): raise DataError('Duplicate candles')
    if any(b['open_ms']-a['open_ms'] != period for a,b in zip(candles,candles[1:])):
        raise DataError('Gap in candle history')
    if len(candles)<limit: raise DataError(f'Insufficient closed candles: {len(candles)}/{limit}')
    return candles[-limit:]


def ohlcv(symbol='BTCUSDT', interval='4h', limit=200):
    try:
        candles=_klines(symbol,interval,limit)
        return {'status':'OK','source':'Binance Spot','symbol':symbol,'interval':interval,
                'closed_only':True,'count':len(candles),'records':candles}
    except (DataError, ValueError, TypeError, KeyError) as e:
        return {'status':'DATA_ERROR','source':'Binance Spot','symbol':symbol,'interval':interval,'reason':str(e),'records':[]}


def _sma(values,period):
    result=[None]*len(values)
    for i in range(period-1,len(values)):
        window=values[i-period+1:i+1]
        if all(v is not None for v in window): result[i]=sum(window)/period
    return result


def _ema(values,period):
    result=[None]*len(values)
    if len(values)<period:return result
    seed=values[:period]
    if any(v is None for v in seed): return result
    prev=sum(seed)/period;result[period-1]=prev
    alpha=2/(period+1)
    for i in range(period,len(values)):
        prev=alpha*values[i]+(1-alpha)*prev
        result[i]=prev
    return result


def _rsi(closes,period=14):
    out=[None]*len(closes)
    if len(closes)<=period:return out
    changes=[closes[i]-closes[i-1] for i in range(1,len(closes))]
    gain=sum(max(c,0) for c in changes[:period])/period
    loss=sum(max(-c,0) for c in changes[:period])/period
    def value(g,l):
        if l==0:return 100.0 if g>0 else 50.0
        return 100-100/(1+g/l)
    out[period]=value(gain,loss)
    for i in range(period+1,len(closes)):
        c=changes[i-1]
        gain=(gain*(period-1)+max(c,0))/period
        loss=(loss*(period-1)+max(-c,0))/period
        out[i]=value(gain,loss)
    return out


def _rolling_sma_nullable(values,period):
    out=[None]*len(values)
    for i in range(period-1,len(values)):
        w=values[i-period+1:i+1]
        if all(v is not None for v in w): out[i]=sum(w)/period
    return out


def indicator_series(closes):
    rsi=_rsi(closes,14)
    rsi_ma=_rolling_sma_nullable(rsi,14)
    raw=[None]*len(closes)
    for i in range(13,len(closes)):
        window=rsi[max(0,i-13):i+1]
        if len(window)==14 and all(x is not None for x in window):
            lo=min(window);hi=max(window)
            raw[i]=0.0 if hi==lo else 100*(rsi[i]-lo)/(hi-lo)
    k=_rolling_sma_nullable(raw,3)
    d=_rolling_sma_nullable(k,3)
    return {'rsi14':rsi, 'rsi_ma14_sma':rsi_ma,'stoch_rsi_k':k,'stoch_rsi_d':d,
            'ema20':_ema(closes,20),'ema50':_ema(closes,50),
            'ema100':_ema(closes,100),'ema200':_ema(closes,200)}


def indicators(symbol='BTCUSDT',interval='4h',history=300):
    try:
        if not isinstance(history,int) or history<250 or history>999:raise DataError('History must be 250..999 candles')
        candles=_klines(symbol,interval,history)
        series=indicator_series([float(c['close']) for c in candles])
        latest={name: (round(seq[-1],10) if seq[-1] is not None else None) for name,seq in series.items()}
        if any(v is None for v in latest.values()): raise DataError('Insufficient indicator warmup')
        return {'status':'OK','source':'Binance Spot','symbol':symbol,'interval':interval,
                'closed_only':True,'close_utc':candles[-1]['close_utc'],'last_close':candles[-1]['close'],
                'parameters':{'rsi_period':14,'rsi_ma_type':'SMA','rsi_ma_period':14,
                              'stoch_rsi_period':14,'stoch_k_smoothing':3,'stoch_d_smoothing':3,
                              'ema_periods':[20,50,100,200],'rsi_method':'Wilder RMA'},
                'history_candles':history,'values':latest}
    except (DataError, ValueError, TypeError, KeyError) as e:
        return {'status':'DATA_ERROR','source':'Binance Spot','symbol':symbol,'interval':interval,'reason':str(e),'values':{}}


def orderbook(symbol='BTCUSDT',limit=100):
    try:
        if symbol not in SYMBOLS:raise DataError('Unsupported symbol')
        if limit not in (5,10,20,50,100,500,1000):raise DataError('Orderbook limit must be 5/10/20/50/100/500/1000')
        data=_request('/api/v3/depth',{'symbol':symbol,'limit':limit})
        bids=data['bids'];asks=data['asks']
        if not bids or not asks:raise DataError('Empty orderbook')
        if len(bids)>limit or len(asks)>limit:raise DataError('Unexpected book size')
        for side in (bids,asks):
            if any(len(l)!=2 or _finite(l[0])<=0 or _finite(l[1])<0 for l in side):raise DataError('Invalid orderbook level')
        bid=float(bids[0][0]);ask=float(asks[0][0]);
        if bid>=ask:raise DataError('Crossed or locked book')
        bid_notional=sum(float(p)*float(q) for p,q in bids)
        ask_notional=sum(float(p)*float(q) for p,q in asks)
        return {'status':'OK','source':'Binance Spot','symbol':symbol,'as_observed_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
                'last_update_id':data['lastUpdateId'],'limit':limit,'best_bid':str(bids[0][0]),
                'best_ask':str(asks[0][0]),'spread_pct':round(100*(ask-bid)/((ask+bid)/2),8),
                'bid_depth_usdt':round(bid_notional,2),'ask_depth_usdt':round(ask_notional,2),
                'imbalance':round((bid_notional-ask_notional)/(bid_notional+ask_notional),6) if bid_notional+ask_notional else None,
                'bids':bids,'asks':asks,
                'note':'REST orderbook snapshot; no continuity guarantee without WebSocket updates'}
    except (DataError, ValueError, TypeError, KeyError) as e:
        return {'status':'DATA_ERROR','source':'Binance Spot','symbol':symbol,'reason':str(e)}
