"""Read-only, UTC-synchronised Binance Spot 4H OHLC data for Kairos BSI."""
from __future__ import annotations
import datetime as dt
import json
import urllib.parse
import urllib.request

BASE = "https://data-api.binance.vision"
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "LINKUSDT", "HYPEUSDT", "HBARUSDT", "SUIUSDT", "ONDOUSDT", "PUMPUSDT", "PLUMEUSDT", "PEPEUSDT", "VIRTUALUSDT")
PERIOD_MS = 4 * 60 * 60 * 1000

class DataError(RuntimeError):
    pass


def fetch_kline(symbol: str, now: dt.datetime | None = None) -> dict:
    if symbol not in SYMBOLS:
        raise DataError(f"Unsupported symbol: {symbol}")
    now = now or dt.datetime.now(dt.timezone.utc)
    now_ms = int(now.timestamp() * 1000)
    params = urllib.parse.urlencode({"symbol": symbol, "interval": "4h", "limit": 3})
    req = urllib.request.Request(BASE + "/api/v3/klines?" + params, headers={"User-Agent": "KairosMarketData/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            candles = json.load(response)
    except Exception as exc:
        raise DataError(f"Binance request failed for {symbol}: {exc}") from exc
    if not isinstance(candles, list) or not candles:
        raise DataError(f"No Binance klines for {symbol}: {candles}")
    closed = [k for k in candles if isinstance(k, list) and len(k) >= 7 and int(k[0]) + PERIOD_MS <= now_ms]
    if not closed:
        raise DataError(f"No completed 4H candle for {symbol}")
    k = closed[-1]
    start_ms = int(k[0]); end_exclusive = start_ms + PERIOD_MS
    if start_ms % PERIOD_MS != 0 or int(k[6]) != end_exclusive - 1:
        raise DataError(f"4H timestamp inconsistency for {symbol}")
    close = float(k[4])
    if close <= 0:
        raise DataError(f"Nonpositive close for {symbol}")
    return {"symbol": symbol, "interval": "4h", "open_ms": start_ms,
            "close_exclusive_ms": end_exclusive, "close_utc": dt.datetime.fromtimestamp(end_exclusive/1000, dt.timezone.utc).isoformat(),
            "close": str(k[4]), "source": "Binance Spot", "pair": symbol}


def synchronized_snapshot(now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    records = []
    failures = {}
    for s in SYMBOLS:
        try:
            records.append(fetch_kline(s, now))
        except DataError as exc:
            failures[s] = str(exc)
    ts = {r["close_exclusive_ms"] for r in records}
    if failures or len(records) != len(SYMBOLS) or len(ts) != 1:
        return {"status": "DATA_ERROR", "certifiable": False, "source": "Binance Spot", "interval": "4h",
                "records": records, "errors": failures, "observed_close_times_ms": sorted(ts),
                "reason": "Missing symbols or unsynchronized confirmed candle close"}
    return {"status": "OK", "certifiable": True, "source": "Binance Spot", "interval": "4h",
            "close_utc": records[0]["close_utc"], "records": records, "errors": {}}
