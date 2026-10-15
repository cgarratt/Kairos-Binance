import datetime as dt
import unittest
from unittest.mock import patch
import macro_fibo as m

BASE=int(dt.datetime(2025,1,1,tzinfo=dt.timezone.utc).timestamp()*1000)
def bar(i,high,low):
    t=BASE+i*m.DAY
    return [t,'100',str(high),str(low),'100','2',t+m.DAY-1,'200',10,'0','0','0']

class MacroFiboTests(unittest.TestCase):
    def test_pagination_and_retracement(self):
        rows=[bar(i, 200 if i==65 else 120, 50 if i==20 else 80) for i in range(70)]
        with patch.object(m,'_request',return_value=rows):
            result=m.macro_fibo('BTCUSDT', '2025-01-01','2025-03-11')
        self.assertEqual(result['status'],'OK')
        self.assertEqual(result['observed_ath']['price'],'200')
        self.assertEqual(result['observed_atl']['price'],'50')
        self.assertEqual(result['swing_low_post_ath']['price'],'80')
        self.assertEqual(result['retracement_from_high']['0.5'],'140.0')
        self.assertEqual(result['approval_status'],'REQUIRES_HUMAN_CONFIRMATION')
    def test_explicit_low(self):
        rows=[bar(i, 200 if i==65 else 120, 50 if i==20 else (70 if i==30 else 80)) for i in range(70)]
        with patch.object(m,'_request',return_value=rows):
            result=m.macro_fibo('BTCUSDT','2025-01-01','2025-03-11','2025-03-10')
        self.assertEqual(result['swing_low_post_ath']['price'],'80')
        self.assertEqual(result['swing_low_post_ath']['method'],'user_selected_post_cycle_peak_daily_low_UNVERIFIED')
    def test_reject_invalid_low(self):
        rows=[bar(i, 200 if i==65 else 120, 50 if i==20 else 80) for i in range(70)]
        with patch.object(m,'_request',return_value=rows):
            self.assertEqual(m.macro_fibo('BTCUSDT','2025-01-01','2025-03-11','2025-01-31')['status'],'DATA_ERROR')
    def test_atl_and_post_ath_are_distinct(self):
        rows=[bar(i, 300 if i==40 else 150, 10 if i==3 else (50 if i==60 else 90)) for i in range(70)]
        with patch.object(m,'_request',return_value=rows):
            result=m.macro_fibo('BTCUSDT','2025-01-01','2025-03-11')
        self.assertEqual(result['observed_atl']['price'],'10')
        self.assertEqual(result['swing_low_post_ath']['price'],'50')
        self.assertFalse(result['swing_low_post_ath']['certified_cycle_low'])
        self.assertEqual(result['retracement_from_high']['0.5'],'175.0')
    def test_ath_last_day_returns_no_cycle_low(self):
        rows=[bar(i, 300 if i==69 else 150, 10 if i==2 else 90) for i in range(70)]
        with patch.object(m,'_request',return_value=rows):
            result=m.macro_fibo('BTCUSDT','2025-01-01','2025-03-11')
        self.assertEqual(result['status'],'OK')
        self.assertIsNone(result['swing_low_post_ath'])
        self.assertIsNone(result['retracement_from_high'])
    def test_cycle_peak_differs_from_ath(self):
        # 2021 historical ATH, but 2025 rally creates lower cycle peak.
        start=dt.datetime(2021,1,1,tzinfo=dt.timezone.utc)
        original_base=globals()['BASE']
        with patch.object(m, '_request') as req:
            rows=[]
            for i in range(1900):
                t=int(start.timestamp()*1000)+i*m.DAY
                peak=53 if i==200 else (31 if i==1580 else 20)
                low=5 if i==100 else (10 if i==1710 else 14)
                rows.append([t,'15',str(peak),str(low),'15','2',t+m.DAY-1,'200',10,'0','0','0'])
            def api(path,params):
                return [r for r in rows if params['startTime']<=r[0]<=params['endTime']][:1000]
            req.side_effect=api
            result=m.macro_fibo('LINKUSDT','2021-01-01','2026-03-15',cycle_start_date='2023-01-01')
        self.assertEqual(result['status'],'OK',result)
        self.assertEqual(result['observed_ath']['price'],'53')
        self.assertEqual(result['observed_atl']['price'],'5')
        self.assertEqual(result['cycle_peak']['price'],'31')
        self.assertEqual(result['swing_low_post_cycle_peak']['price'],'10')
        self.assertEqual(result['retracement_from_high']['0.5'],'20.5')
    def test_invalid_cycle_date(self):
        rows=[bar(i,200 if i==65 else 120,80) for i in range(70)]
        with patch.object(m,'_request',return_value=rows):
            result=m.macro_fibo('BTCUSDT','2025-01-01','2025-03-11',cycle_start_date='2027-01-01')
        self.assertEqual(result['status'],'DATA_ERROR')
    def test_legacy_close_time_within_utc_day(self):
        rows=[bar(i, 200 if i==65 else 120, 50 if i==20 else 80) for i in range(70)]
        rows[4][6] -= 500  # valid same-day close metadata, noncanonical millisecond
        with patch.object(m,'_request',return_value=rows):
            result=m.macro_fibo('BTCUSDT','2025-01-01','2025-03-11')
        self.assertEqual(result['status'],'OK')

    def test_cross_day_close_rejected(self):
        rows=[bar(i,120,80) for i in range(70)]
        rows[2][6]=rows[2][0]+m.DAY
        with patch.object(m,'_request',return_value=rows):
            result=m.macro_fibo('BTCUSDT','2025-01-01','2025-03-11')
        self.assertEqual(result['status'],'DATA_ERROR')
        self.assertIn('Cross-day',result['reason'])

    def test_invalid_prices_report_date(self):
        rows=[bar(i,120,80) for i in range(70)]
        rows[5][3]='0'
        with patch.object(m,'_request',return_value=rows):
            result=m.macro_fibo('BTCUSDT','2025-01-01','2025-03-11')
        self.assertEqual(result['status'],'DATA_ERROR')
        self.assertIn('2025-01-06',result['reason'])

    def test_gap_fails_closed(self):
        rows=[bar(i,110,80) for i in range(70) if i!=40]
        with patch.object(m,'_request',return_value=rows):
            result=m.macro_fibo('BTCUSDT','2025-01-01','2025-03-11')
        self.assertEqual(result['status'],'DATA_ERROR')
    def test_unlisted_symbol(self):
        self.assertEqual(m.macro_fibo('DOGEUSDT')['status'],'DATA_ERROR')
    def test_missing_history(self):
        with patch.object(m,'_request',return_value=[]):
            self.assertEqual(m.macro_fibo('BTCUSDT')['status'],'DATA_ERROR')
    def test_page_continuity(self):
        rows=[bar(i,120,80) for i in range(1005)]
        def api(path,params):
            after=params['startTime'];before=params['endTime']
            return [r for r in rows if after<=r[0]<=before][:1000]
        with patch.object(m,'_request',side_effect=api):
            hist,pages=m.fetch_history('BTCUSDT','2025-01-01','2027-10-02',now=dt.datetime(2028,1,1,tzinfo=dt.timezone.utc))
        self.assertEqual(len(hist),1005)
        self.assertEqual(pages,2)

if __name__=='__main__':unittest.main()
