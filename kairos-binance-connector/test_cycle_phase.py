import unittest
from unittest.mock import patch
from decimal import Decimal
from datetime import datetime,timezone,timedelta
import cycle_phase as c
BASE=datetime(2024,4,20,tzinfo=timezone.utc)
def bar(i,high,low):
    return {'open_ms':int((BASE+timedelta(days=i)).timestamp()*1000),'high':Decimal(str(high)),'low':Decimal(str(low))}
class CyclePhaseTests(unittest.TestCase):
    def test_ch_then_cl_and_pivot_sequence(self):
        rows=[bar(i,100,80) for i in range(100)]
        rows[10]=bar(10,200,80)
        rows[20]=bar(20,110,40)
        for i,h,l in [(30,100,90),(31,110,95),(32,150,100),(33,110,90),(34,105,90),
                      (39,110,80),(40,105,65),(41,110,85),
                      (49,130,100),(50,190,120),(51,130,100)]: rows[i]=bar(i,h,l)
        with patch.object(c,'fetch_history',return_value=(rows,1)):
            r=c.cycle_phase('BTCUSDT',min_reversal_pct=5)
        self.assertEqual(r['status'],'OK');self.assertEqual(r['cycle_high']['price'],'200')
        self.assertEqual(r['cycle_low']['price'],'40')
        self.assertTrue(r['wave_pivots'].get('SH1'))
        self.assertIn('O2',r['projections'])
        self.assertIsNone(r['confirmed_wave'])
    def test_manual_requires_four_fields(self):
        with patch.object(c,'fetch_history',return_value=([bar(i,100,80) for i in range(40)],1)):
            r=c.cycle_phase('HYPEUSDT',historical_ch=59)
        self.assertEqual(r['status'],'DATA_ERROR')
    def test_recent_peak_no_low(self):
        rows=[bar(i,100+i,50) for i in range(35)]
        with patch.object(c,'fetch_history',return_value=(rows,1)):
            r=c.cycle_phase('BTCUSDT')
        self.assertEqual(r['phase'],'AWAITING_CYCLE_LOW')
    def test_insufficient_history(self):
        with patch.object(c,'fetch_history',return_value=([bar(i,100,80) for i in range(10)],1)):
            self.assertEqual(c.cycle_phase()['status'],'DATA_ERROR')
    def test_manual_history(self):
        rows=[bar(i,100,80) for i in range(40)]
        with patch.object(c,'fetch_history',return_value=(rows,1)):
            r=c.cycle_phase('HYPEUSDT',historical_ch=59,historical_cl=20.5,historical_ch_date='2024-04-22',historical_cl_date='2024-04-25')
        self.assertEqual(r['status'],'OK')
        self.assertEqual(r['cycle_low']['price'],'20.5')
        self.assertEqual(r['cycle_high']['source'],'USER_SUPPLIED_HISTORICAL_UNVERIFIED')
if __name__=='__main__':unittest.main()
