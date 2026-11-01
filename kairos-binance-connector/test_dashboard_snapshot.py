import unittest
from unittest.mock import patch
import dashboard_snapshot as d
from binance_http import RateLimitError
import time

class DashboardSnapshotTests(unittest.TestCase):
    def setUp(self):d._CACHE=None
    def tearDown(self):d._CACHE=None
    def test_batch_reuses_histories_and_indicators_without_extra_fetches(self):
        candles=[{'open_ms':0,'close_utc':'2020-01-02T00:00:00Z','high':'2','low':'1','close':'1.5'}]*300
        spot={'status':'OK','as_observed_utc':'fixed-time','records':[{'symbol':'BTCUSDT'}]}
        with patch.object(d,'SYMBOLS',['BTCUSDT']),patch.object(d,'spot_prices',return_value=spot) as prices,patch.object(d,'_klines',return_value=candles) as history,patch.object(d,'cycle_phase',return_value={'status':'OK'}) as cycles:
            a=d.dashboard_snapshot();a['spot']['records'].clear()
            b=d.dashboard_snapshot()
            self.assertEqual(prices.call_count,1)
            self.assertEqual(history.call_count,1)
            self.assertEqual(cycles.call_count,1)
            self.assertTrue(b['spot']['records'])
            self.assertEqual(b['indicators']['BTCUSDT:1d']['status'],'OK')
            self.assertEqual(b['as_observed_utc'],'fixed-time')
    def test_blocked_spot_does_not_fan_out(self):
        with patch.object(d,'spot_prices',return_value={'status':'DATA_ERROR','http_status':418}),patch.object(d,'_klines') as history:
            self.assertEqual(d.dashboard_snapshot()['http_status'],418)
            history.assert_not_called();self.assertIsNone(d._CACHE)
    def test_block_mid_bundle_stops_immediately_and_never_publishes_partial(self):
        with patch.object(d,'spot_prices',return_value={'status':'OK'}),patch.object(d,'_klines',side_effect=RateLimitError(429,time.time()+60)) as history:
            result=d.dashboard_snapshot()
            self.assertEqual(result['http_status'],429)
            history.assert_called_once();self.assertIsNone(d._CACHE)
