import unittest
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from unittest.mock import patch
import cycle_phase as c
MON=datetime(2024,4,22,tzinfo=timezone.utc)
def daily(week,day,high=105,low=95,close=100):
    t=MON+timedelta(days=week*7+day)
    return {'open_ms':int(t.timestamp()*1000),'high':Decimal(str(high)),
            'low':Decimal(str(low)),'close':Decimal(str(close))}
class WeeklyBOSTests(unittest.TestCase):
    def test_incomplete_week_excluded(self):
        rows=[daily(0,d) for d in range(7)]+[daily(1,d) for d in range(4)]
        self.assertEqual(len(c.weekly_bars(rows)),1)
    def test_5_left_5_right_and_no_lookahead(self):
        weeks=c.weekly_bars([daily(w,d,high=150 if w==7 else 105) for w in range(13) for d in range(7)])
        peaks=[p for p in c.weekly_pivots(weeks) if p['kind']=='SH']
        self.assertEqual(len(peaks),1)
        self.assertEqual((peaks[0]['index'],peaks[0]['confirmed_index']),(7,12))
        self.assertFalse(c.weekly_pivots(weeks[:12]))
    def test_no_bos_means_no_transition(self):
        rows=[daily(w,d,high=200 if w==1 else 120,low=40 if w==3 else 90,close=100) for w in range(36) for d in range(7)]
        with patch.object(c,'fetch_history',return_value=(rows,1)):
            r=c.cycle_phase('BTCUSDT')
        self.assertEqual(r['status'],'OK')
        self.assertEqual(r['phase'],'O1')
        self.assertEqual(r['wave_pivots'],{})
        self.assertEqual(r['pivot_method']['left_weeks'],5)
        self.assertEqual(r['pivot_method']['right_weeks'],5)
    def test_manual_anchor_hype_kept(self):
        rows=[daily(w,d) for w in range(20) for d in range(7)]
        with patch.object(c,'fetch_history',return_value=(rows,1)):
            r=c.cycle_phase('HYPEUSDT',historical_ch=59,historical_cl=20.5,
              historical_ch_date='2024-04-22',historical_cl_date='2024-04-25')
        self.assertEqual(r['status'],'OK')
        self.assertEqual(r['cycle_low']['price'],'20.5')
        self.assertIsNone(r['confirmed_wave'])
if __name__=='__main__':unittest.main()
