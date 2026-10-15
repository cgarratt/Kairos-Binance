"""Exploratory BTC-halving H4 cycle / wave state. Public Binance daily candles only.
No orders, wallet state, or approved anchors are modified.
"""
from decimal import Decimal
from datetime import date
from macro_fibo import fetch_history, _iso, _day_ms
from market_data import DataError

H4_START='2024-04-20'
FIB_RETRACE=('0.382','0.5','0.618','0.786')
FIB_EXT=('1.618','2.618','3.618','4.618')

def _point(c, field, origin):
    return {'price':format(c[field],'f'),'date_utc':_iso(c['open_ms']),'source':origin}

def _pivots(candles, radius=3, min_reversal_pct=8):
    """Closed weekly-style 7-bar local peaks/troughs; avoid lookahead at newest bars.
    A pivot requires a strictly greater/lower extreme than all 3 preceding and following
    closed daily bars, plus a threshold reversal on either side.
    """
    found=[]; n=len(candles); threshold=Decimal(str(min_reversal_pct))/100
    for i in range(radius,n-radius):
        c=candles[i]; left=candles[i-radius:i]; right=candles[i+1:i+1+radius]
        if all(c['high']>a['high'] for a in left+right) and all((c['high']-min(a['low'] for a in side))/c['high']>=threshold for side in (left,right)):
            found.append(('SH',c))
        if all(c['low']<a['low'] for a in left+right) and all((max(a['high'] for a in side)-c['low'])/c['low']>=threshold for side in (left,right)):
            found.append(('SL',c))
    return sorted(found,key=lambda p:p[1]['open_ms'])

def _levels(a,b,root, ratios, kind):
    x=a['high'] if kind=='down' else a['low']; y=b['high'] if kind=='down' else b['high']
    if kind=='down':
        return {r:format(y-(y-x)*Decimal(r),'f') for r in ratios}
    return {r:format(root['low']+(y-x)*Decimal(r),'f') for r in ratios}

def cycle_phase(symbol='BTCUSDT', h4_start=H4_START, historical_ch=None, historical_cl=None,
                historical_ch_date=None, historical_cl_date=None, pivot_radius=3,
                min_reversal_pct=8):
    """H4 CH -> post-CH CL -> confirmed structural pivots; projections conditional.
    Manual CH+CL must be paired with dates, ordered, and are unverified external anchors.
    """
    try:
        if h4_start!=H4_START: raise DataError('Only BTC halving H4 starting 2024-04-20 is supported in v5.3')
        if not 2<=pivot_radius<=10 or not 2<=min_reversal_pct<=35: raise DataError('Invalid pivot settings')
        bars,pages=fetch_history(symbol,start_date=h4_start)
        if len(bars)<20: raise DataError('Need >=20 closed daily candles')
        manual=any(x is not None for x in (historical_ch,historical_cl,historical_ch_date,historical_cl_date))
        if manual and not all(x is not None for x in (historical_ch,historical_cl,historical_ch_date,historical_cl_date)):
            raise DataError('Manual historical CH/CL require both prices and both dates')
        if manual:
            ch=Decimal(str(historical_ch));cl=Decimal(str(historical_cl))
            ct=_day_ms(historical_ch_date);lt=_day_ms(historical_cl_date)
            if not(ch>cl>0 and ct<lt and lt<bars[-1]['open_ms']+86400000):raise DataError('Historical CH/CL prices or chronology invalid')
            chp={'price':format(ch,'f'),'date_utc':_iso(ct),'source':'USER_SUPPLIED_HISTORICAL_UNVERIFIED'}
            clp={'price':format(cl,'f'),'date_utc':_iso(lt),'source':'USER_SUPPLIED_HISTORICAL_UNVERIFIED'}
            post=[b for b in bars if b['open_ms']>lt]
        else:
            high=max(bars,key=lambda b:b['high']); after=[b for b in bars if b['open_ms']>high['open_ms']]
            chp=_point(high,'high','BINANCE_SPOT_H4_CANDIDATE')
            if not after:
                return {'status':'OK','symbol':symbol,'scope':'EXPLORATORY_ONLY','cycle':'H4','cycle_high':chp,'cycle_low':None,'phase':'AWAITING_CYCLE_LOW','confirmed_wave':None,'candidate_wave':None,'wave_pivots':{},'projections':{},'approval_status':'REQUIRES_HUMAN_CONFIRMATION'}
            low=min(after,key=lambda b:b['low']);clp=_point(low,'low','BINANCE_SPOT_POST_CH_PROVISIONAL')
            post=[b for b in bars if b['open_ms']>low['open_ms']]
        pivots=_pivots(post,pivot_radius,min_reversal_pct) if len(post)>=pivot_radius*2+1 else []
        needed=['SH','SL','SH','SL','SH']; names=['SH1','SL1','SH2','SL2','SH3']
        selected=[]; last_time=-1
        for kind in needed:
            matching=next(((k,b) for k,b in pivots if k==kind and b['open_ms']>last_time),None)
            if matching is None:break
            selected.append(matching[1]);last_time=matching[1]['open_ms']
        waves={names[i]:_point(b, 'high' if i%2==0 else 'low','BINANCE_STRUCTURAL_PIVOT_CANDIDATE') for i,b in enumerate(selected)}
        order=['O1','O2','O3','O4','O5']; confirmed=order[len(selected)-1] if selected else None
        current=order[len(selected)] if len(selected)<5 else 'POST_O5_CANDIDATE'
        projections={}
        # O2: retracement from CL to observed SH1
        if len(selected)>=1:
            low=Decimal(clp['price']);high=selected[0]['high']
            if high>low:projections['O2']={r:format(high-(high-low)*Decimal(r),'f') for r in FIB_RETRACE}
        # O3 3-point extension: CL -> SH1 -> SL1
        if len(selected)>=2:
            low=Decimal(clp['price']);high=selected[0]['high'];base=selected[1]['low']
            if high>low:projections['O3']={r:format(base+(high-low)*Decimal(r),'f') for r in FIB_EXT}
        if len(selected)>=3:
            low=selected[1]['low'];high=selected[2]['high']
            if high>low:projections['O4']={r:format(high-(high-low)*Decimal(r),'f') for r in FIB_RETRACE}
        if len(selected)>=4:
            low=selected[1]['low'];high=selected[2]['high'];base=selected[3]['low']
            if high>low:projections['O5']={r:format(base+(high-low)*Decimal(r),'f') for r in FIB_EXT}
        return {'status':'OK','symbol':symbol,'source':'Binance Spot closed 1d + optional user historical anchors',
                'scope':'EXPLORATORY_ONLY','approval_status':'REQUIRES_HUMAN_CONFIRMATION',
                'cycle':'H4','halving_start':H4_START,'cycle_high':chp,'cycle_low':clp,
                'cycle_low_certified':False,'phase':current,'confirmed_wave':None,
                'structural_wave_candidates':list(waves),'candidate_wave':current,'wave_pivots':waves,
                'projections':projections,'pivot_method':{'radius_closed_daily_bars':pivot_radius,
                  'minimum_reversal_pct':min_reversal_pct,'confirmation':'3 later CLOSED daily bars; candidate only'},
                'coverage':{'daily_candles':len(bars),'pages':pages,'post_cl_candles':len(post)},
                'warning':'Wave pivots are algorithmic CANDIDATES, not certified Elliott waves. CL and pivots require human review; never modify approved anchors or orders.'}
    except (DataError,ValueError,TypeError,ArithmeticError) as e:
        return {'status':'DATA_ERROR','symbol':symbol,'reason':str(e),'approval_status':'NOT_APPROVED'}
