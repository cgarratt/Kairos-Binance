import io
import tempfile
import unittest
import urllib.error
from unittest.mock import patch
import binance_http as h
import market_intelligence as m

class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=patch.object(h,'STATE_PATH',self.temp.name+'/guard.db');self.path.start()
        self.sleep=patch.object(h.time,'sleep');self.sleep.start()
        m._SPOT_CACHE.clear()
    def tearDown(self):
        m._SPOT_CACHE.clear();self.path.stop();self.sleep.stop();self.temp.cleanup()
    def error(self,code=418,headers=None,body=b''):
        return urllib.error.HTTPError('https://example.test',code,'limited',headers or {},io.BytesIO(body))
    def test_418_shared_pause_and_persistence(self):
        with patch.object(h.urllib.request,'urlopen',side_effect=self.error(headers={'Retry-After':'600'})) as net:
            with self.assertRaises(h.RateLimitError):h.request_json('/api/v3/ticker/price',{})
            with self.assertRaises(h.RateLimitError):h.request_json('/api/v3/klines',{'symbol':'ETHUSDT'})
            self.assertEqual(net.call_count,1)
            self.assertGreater(h._state()[0],h.time.time()+590)
    def test_ban_timestamp_takes_longer_than_retry_header(self):
        until=int((h.time.time()+1800)*1000)
        deadline=h._deadline(self.error(headers={'Retry-After':'60'}),'IP banned until '+str(until),h.time.time())
        self.assertAlmostEqual(deadline,until/1000)
    def test_429_not_immediately_retried(self):
        with patch.object(h.urllib.request,'urlopen',side_effect=self.error(429)) as net:
            for _ in range(2):
                with self.assertRaises(h.RateLimitError):h.request_json('/api/v3/klines',{})
            self.assertEqual(net.call_count,1)
    def test_expired_pause_allows_request(self):
        h._state(h.time.time()-10,418)
        with patch.object(h.urllib.request,'urlopen') as net:
            net.return_value.__enter__.return_value=io.BytesIO(b'{"ok":true}')
            self.assertEqual(h.request_json('/api/v3/time',{}),{'ok':True})
    def test_no_retry_or_host_switch_for_other_http_error(self):
        with patch.object(h.urllib.request,'urlopen',side_effect=self.error(403)) as net:
            with self.assertRaises(h.DataError):h.request_json('/api/v3/time',{})
            self.assertEqual(net.call_count,1)
    def test_bsi_path_uses_same_guard(self):
        import market_data
        h._state(h.time.time()+100,418)
        with patch.object(h.urllib.request,'urlopen') as net:
            result=market_data.synchronized_snapshot()
            self.assertEqual(result['status'],'DATA_ERROR');net.assert_not_called()
    def test_spot_cache_preserves_timestamp_and_copies(self):
        result={'status':'OK','as_observed_utc':'fixed-observation','records':[{'symbol':'BTCUSDT'}]}
        with patch.object(m,'_spot_prices_uncached',return_value=result) as fetch:
            a=m.spot_prices(['BTCUSDT']);a['records'].clear()
            b=m.spot_prices(['BTCUSDT'])
            self.assertEqual(fetch.call_count,1)
            self.assertEqual(b['as_observed_utc'],'fixed-observation');self.assertTrue(b['records'])
    def test_failures_never_cached_as_prices(self):
        with patch.object(m,'_spot_prices_uncached',return_value={'status':'DATA_ERROR','records':[]}) as fetch:
            m.spot_prices(['BTCUSDT']);m.spot_prices(['BTCUSDT'])
            self.assertEqual(fetch.call_count,2);self.assertFalse(m._SPOT_CACHE)
    def test_spot_cache_expiry(self):
        m._SPOT_CACHE[('BTCUSDT',)]=(h.time.monotonic()-61,{'status':'OK','records':['old']})
        with patch.object(m,'_spot_prices_uncached',return_value={'status':'DATA_ERROR','records':[]}) as fetch:
            self.assertEqual(m.spot_prices(['BTCUSDT'])['status'],'DATA_ERROR');fetch.assert_called_once()
    def test_spot_exposes_cooldown_without_fake_prices(self):
        h._state(h.time.time()+120,418)
        with patch.object(h.urllib.request,'urlopen') as net:
            result=m.spot_prices(['BTCUSDT'])
            self.assertEqual(result['http_status'],418)
            self.assertIn('retry_at_utc',result)
            self.assertEqual(result['records'],[]);net.assert_not_called()
    def test_http_date_retry_after(self):
        from email.utils import formatdate
        deadline=h.time.time()+500
        actual=h._deadline(self.error(429,{'Retry-After':formatdate(deadline,usegmt=True)}),'',h.time.time())
        self.assertAlmostEqual(actual,deadline,delta=1)
    def test_network_calls_serialized(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        active=0;peak=0;lock=threading.Lock()
        def network(*args,**kwargs):
            nonlocal active,peak
            with lock:active+=1;peak=max(peak,active)
            threading.Event().wait(.02)
            with lock:active-=1
            from contextlib import nullcontext
            return nullcontext(io.BytesIO(b'{}'))
        with patch.object(h.urllib.request,'urlopen',side_effect=network):
            with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda _:h.request_json('/api/v3/time',{}),range(4)))
        self.assertEqual(peak,1)
    def test_closed_history_cache_shared_and_survives_pause(self):
        params={'symbol':'BTCUSDT','interval':'1d','startTime':0,'endTime':1000,'limit':1000}
        from contextlib import nullcontext
        with patch.object(h.urllib.request,'urlopen',side_effect=lambda *a,**k:nullcontext(io.BytesIO(b'[[1,2,3]]'))) as net:
            first=h.request_json('/api/v3/klines',params)
            h._state(h.time.time()+600,418)
            self.assertEqual(h.request_json('/api/v3/klines',params),first)
            self.assertEqual(net.call_count,1)
    def test_forming_raw_candle_cache_rotates_at_boundary(self):
        params={'symbol':'BTCUSDT','interval':'1h','limit':100}
        a=h._cache_spec('/api/v3/klines',params,7201)
        b=h._cache_spec('/api/v3/klines',params,10801)
        self.assertNotEqual(a[0],b[0]);self.assertEqual(a[1],10800)
        self.assertIsNone(h._cache_spec('/api/v3/ticker/price',{},7201))
    def test_telemetry_preserves_weight_and_tool_without_urls(self):
        @h.audited_tool
        def get_kairos_macro_fibo():
            h._audit('/api/v3/klines',{'symbol':'BTCUSDT','interval':'1d'},200,{'X-MBX-USED-WEIGHT-1M':'120','Authorization':'hidden'})
        with self.assertLogs('kairos.binance',level='INFO') as log:get_kairos_macro_fibo()
        message=' '.join(log.output)
        self.assertIn('get_kairos_macro_fibo',message);self.assertIn('120',message)
        self.assertNotIn('hidden',message);self.assertNotIn('Authorization',message)
