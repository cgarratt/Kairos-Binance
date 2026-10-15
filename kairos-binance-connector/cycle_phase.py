"""Kairos H4 exploratory phase: weekly 5L/5R pivot plus weekly-close BOS.
No approved anchors, orders, or custody are modified. Daily history is aggregated
into CLOSED UTC Monday-Sunday weeks, with incomplete last week excluded.
"""
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from macro_fibo import fetch_history, _iso, _day_ms
from market_data import DataError

H4_START='2024-04-20'
RETRACE=('0.382','0.5','0.618','0.786')
EXT=('1.618','2.618','3.618','4.618')
WEEK_MS=7*86400000

def _point(bar,field,source):
    return {'price':format(bar[field],'f'),'date_utc':_iso(bar['open_ms']),'source':source}

def weekly_bars(daily):
    """Fully covered UTC Monday-Sunday weeks, not a currently forming week."""
    groups={}
    for b in sorted(daily,key=lambda x:x['open_ms']):
        d=datetime.fromtimestamp(b['open_ms']/1000,tz=timezone.utc)
        monday=(d-timedelta(days=d.weekday())).date()
        groups.setdefault(monday,[]).append(b)
    out=[]
    for monday,bs in sorted(groups.items()):
        days=[datetime.fromtimestamp(b['open_ms']/1000,tz=timezone.utc).date() for b in bs]
        if len(bs)!=7 or len(set(days))!=7 or days[0]!=monday or days[-1]!=monday+timedelta(days=6):continue
        out.append({'open_ms':bs[0]['open_ms'],'high':max(b['high'] for b in bs),
                    'low':min(b['low'] for b in bs),'close':bs[-1].get('close',(bs[-1]['high']+bs[-1]['low'])/2),
                    'close_ms':bs[-1]['open_ms']+86400000})
    return out

def weekly_pivots(weeks,radius=5):
    pivots=[]
    for i in range(radius,len(weeks)-radius):
        w=weeks[i];side=weeks[i-radius:i]+weeks[i+1:i+radius+1]
        # A 5R pivot can only be confirmed after the fifth right week closes.
        if all(w['high']>a['high'] for a in side):pivots.append({'kind':'SH','bar':w,'index':i,'confirmed_index':i+radius})
        if all(w['low']<a['low'] for a in side):pivots.append({'kind':'SL','bar':w,'index':i,'confirmed_index':i+radius})
    return sorted(pivots,key=lambda p:(p['confirmed_index'],p['index']))

def d_dummy(points,name):
    return Decimal(points[name]['price'])

def cycle_phase(symbol='BTCUSDT',h4_start=H4_START,historical_ch=None,historical_cl=None,
                historical_ch_date=None,historical_cl_date=None,pivot_radius=5,min_reversal_pct=8):
    try:
        if h4_start!=H4_START:raise DataError('H4 halving start is fixed at 2024-04-20')
        if pivot_radius!=5:raise DataError('Macro confirmation requires weekly pivot radius 5L/5R')
        bars,pages=fetch_history(symbol,start_date=h4_start)
        if len(bars)<20:raise DataError('Need >=20 closed daily candles')
        manual=any(x is not None for x in (historical_ch,historical_cl,historical_ch_date,historical_cl_date))
        if manual and not all(x is not None for x in (historical_ch,historical_cl,historical_ch_date,historical_cl_date)):
            raise DataError('Historical CH/CL require both prices and both dates')
        if manual:
            ch=Decimal(str(historical_ch));cl=Decimal(str(historical_cl));ct=_day_ms(historical_ch_date);lt=_day_ms(historical_cl_date)
            if not(ch>cl>0 and ct<lt and lt<=bars[-1]['open_ms']):raise DataError('Invalid historical anchors')
            chp={'price':format(ch,'f'),'date_utc':_iso(ct),'source':'USER_SUPPLIED_UNVERIFIED'}
            clp={'price':format(cl,'f'),'date_utc':_iso(lt),'source':'USER_SUPPLIED_UNVERIFIED'}
            after=[b for b in bars if b['open_ms']>lt]
        else:
            ch=max(bars,key=lambda b:b['high']); later=[b for b in bars if b['open_ms']>ch['open_ms']]
            chp=_point(ch,'high','BINANCE_H4_CANDIDATE')
            if not later:return {'status':'OK','symbol':symbol,'phase':'AWAITING_CYCLE_LOW','cycle_high':chp,'cycle_low':None,'confirmed_wave':None,'candidate_wave':None,'wave_pivots':{},'projections':{},'scope':'EXPLORATORY_ONLY'}
            cl=min(later,key=lambda b:b['low']);clp=_point(cl,'low','BINANCE_POST_CH_PROVISIONAL')
            after=[b for b in bars if b['open_ms']>cl['open_ms']]
        weeks=weekly_bars(bars)
        pivots=weekly_pivots(weeks)
        cl_time=_day_ms(clp['date_utc'][:10]); selected={}; event_log=[]
        # Active state evolves only at CLOSED weekly confirmation, no daily pivot shortcuts.
        # BOS break of protected weekly swing low/high, on closing basis, AFTER pivot confirmation.
        targets=[('SH1','SH','bear','SL'),('SL1','SL','bull','SH'),('SH2','SH','bear','SL'),('SL2','SL','bull','SH'),('SH3','SH','bear','SL')]
        last_pivot_time=cl_time
        last_transition_week=-1
        for label,kind,direction,protected_kind in targets:
            chosen=None
            for p in pivots:
                if p['kind']!=kind or p['bar']['open_ms']<=last_pivot_time or p['confirmed_index']<=last_transition_week:continue
                if label=='SH1' and p['bar']['high']<=Decimal(clp['price']):continue
                if label=='SL1' and p['bar']['low']>=d_dummy(selected,'SH1'):continue
                if label=='SH2' and p['bar']['high']<=d_dummy(selected,'SL1'):continue
                if label=='SL2' and p['bar']['low']>=d_dummy(selected,'SH2'):continue
                if label=='SH3' and p['bar']['high']<=d_dummy(selected,'SL2'):continue
                # Structural level is the most recent *opposite* weekly pivot, confirmed before target pivot.
                prior=[q for q in pivots if q['kind']==protected_kind and q['index']<p['index'] and q['confirmed_index']<=p['confirmed_index']]
                if not prior:continue
                protected=prior[-1]['bar']['low' if direction=='bear' else 'high']
                for j in range(p['confirmed_index']+1,len(weeks)):
                    close=weeks[j]['close']
                    if (direction=='bear' and close<protected) or (direction=='bull' and close>protected):
                        chosen=(p,j,protected);break
                if chosen:break
            if not chosen:break
            p,j,level=chosen
            selected[label]=_point(p['bar'],'high' if kind=='SH' else 'low','WEEKLY_5L5R_PLUS_CLOSE_BOS_CANDIDATE')
            event_log.append({'wave':label,'pivot_confirmation_utc':_iso(weeks[p['confirmed_index']]['close_ms']),
                              'bos_close_utc':_iso(weeks[j]['close_ms']),'bos_level':format(level,'f'),
                              'direction':direction})
            last_pivot_time=p['bar']['open_ms'];last_transition_week=j
        projections={}
        d=lambda k:Decimal(selected[k]['price'])
        cl=Decimal(clp['price'])
        if 'SH1' in selected and d('SH1')>cl:
            projections['O2']={r:format(d('SH1')-(d('SH1')-cl)*Decimal(r),'f') for r in RETRACE}
        if 'SL1' in selected and d('SH1')>cl:
            projections['O3']={r:format(d('SL1')+(d('SH1')-cl)*Decimal(r),'f') for r in EXT}
        if 'SH2' in selected and d('SH2')>d('SL1'):
            projections['O4']={r:format(d('SH2')-(d('SH2')-d('SL1'))*Decimal(r),'f') for r in RETRACE}
        if 'SL2' in selected and d('SH2')>d('SL1'):
            projections['O5']={r:format(d('SL2')+(d('SH2')-d('SL1'))*Decimal(r),'f') for r in EXT}
        stages=['O1','O2','O3','O4','O5'];idx=len(selected)
        return {'status':'OK','symbol':symbol,'source':'Binance Spot closed daily aggregated to full UTC weeks',
                'cycle':'H4','scope':'EXPLORATORY_ONLY','approval_status':'REQUIRES_HUMAN_CONFIRMATION',
                'cycle_high':chp,'cycle_low':clp,'cycle_low_certified':False,
                'phase':stages[idx] if idx<5 else 'POST_O5_CANDIDATE',
                'confirmed_wave':None,'candidate_wave':stages[idx] if idx<5 else 'POST_O5_CANDIDATE',
                'wave_pivots':selected,'structural_wave_candidates':list(selected),
                'bos_events':event_log,'projections':projections,
                'pivot_method':{'timeframe':'1w','left_weeks':5,'right_weeks':5,'bos':'weekly close beyond protected opposite weekly pivot AFTER pivot confirmation'},
                'coverage':{'daily_candles':len(bars),'full_weeks':len(weeks),'pages':pages,'post_cl_candles':len(after)},
                'warning':'Weekly 5L/5R and close BOS are necessary but not sufficient for Elliott certification. Unapproved; read only.'}
    except (DataError,ValueError,TypeError,ArithmeticError) as e:
        return {'status':'DATA_ERROR','symbol':symbol,'reason':str(e),'approval_status':'NOT_APPROVED'}
