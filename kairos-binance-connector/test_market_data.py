import datetime as dt
import unittest
from unittest.mock import patch
import market_data as m

class Tests(unittest.TestCase):
    def test_btc_not_implicitly_certified(self):
        with patch.object(m, "fetch_kline", side_effect=lambda sym,now: {"symbol":sym,"close_exclusive_ms":100 if sym!="PLUMEUSDT" else 200}):
            result=m.synchronized_snapshot(dt.datetime.now(dt.timezone.utc))
        self.assertEqual(result["status"], "DATA_ERROR")
        self.assertFalse(result["certifiable"])

    def test_all_coincident(self):
        with patch.object(m, "fetch_kline", side_effect=lambda sym,now: {"symbol":sym,"close_exclusive_ms":100,"close_utc":"t"}):
            result=m.synchronized_snapshot(dt.datetime.now(dt.timezone.utc))
        self.assertTrue(result["certifiable"])
        self.assertEqual(len(result["records"]),12)

    def test_one_missing(self):
        def fake(sym, now):
            if sym=="HYPEUSDT": raise m.DataError("unsupported")
            return {"symbol": sym, "close_exclusive_ms":100}
        with patch.object(m,"fetch_kline",side_effect=fake):
            result=m.synchronized_snapshot(dt.datetime.now(dt.timezone.utc))
        self.assertFalse(result["certifiable"])
        self.assertIn("HYPEUSDT",result["errors"])

if __name__ == '__main__': unittest.main()
