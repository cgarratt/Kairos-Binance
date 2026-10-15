import unittest
from unittest.mock import patch
import market_intelligence as m

class Tests(unittest.TestCase):
    def test_rsi_constant(self):
        self.assertEqual(m._rsi([100]*40)[-1],50)
    def test_rsi_rising(self):
        self.assertEqual(m._rsi(list(range(1,45)))[-1],100)
    def test_ema_constant(self):
        self.assertAlmostEqual(m._ema([5]*250,200)[-1],5)
    def test_indicators_ready(self):
        seq=m.indicator_series([100+i*.1+(i%7)*.05 for i in range(300)])
        self.assertTrue(all(v[-1] is not None for v in seq.values()))
    def test_reject_other_pairs(self):
        self.assertEqual(m.spot_prices(['DOGEUSDT'])['status'],'DATA_ERROR')
    def test_price_synthetic(self):
        def api(path,params):
            syms=['BTCUSDT']
            if path.endswith('/price'):return [{'symbol':'BTCUSDT','price':'100.00'}]
            return [{'symbol':'BTCUSDT','bidPrice':'99.9','askPrice':'100.1','bidQty':'2','askQty':'3'}]
        with patch.object(m,'_request',side_effect=api):
            d=m.spot_prices(['BTCUSDT'])
        self.assertEqual(d['status'],'OK');self.assertAlmostEqual(d['records'][0]['spread_pct'],.2)
    def test_orderbook_synthetic(self):
        with patch.object(m,'_request',return_value={'lastUpdateId':1,'bids':[['99','2']],'asks':[['101','1']]}):
            d=m.orderbook('BTCUSDT',5)
        self.assertEqual(d['status'],'OK');self.assertEqual(d['bid_depth_usdt'],198)
    def test_unclosed_rejected(self):
        # 4h aligned current unfinished candle only
        import datetime as dt
        start=(int(dt.datetime.now(dt.timezone.utc).timestamp()*1000)//14400000)*14400000
        data=[[start,'100','101','99','100','1',start+14400000-1,'100','1','0','0','0']]
        with patch.object(m,'_request',return_value=data):
            d=m.ohlcv('BTCUSDT','4h',1)
        self.assertEqual(d['status'],'DATA_ERROR')

if __name__=='__main__':unittest.main()
