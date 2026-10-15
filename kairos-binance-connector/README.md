# Kairos Binance Market Data — private read-only connector

Provides one MCP tool, `get_kairos_bsi_4h_closes`, for twelve Binance Spot `*USDT` symbols. No Binance account, API key, custody, trades, or write scopes.

## Run

Requires Python 3.12+ with internet access to `data-api.binance.vision`.

```bash
pip install -r requirements.txt
python server.py
```

Container alternative: `docker build -t kairos-binance .` then `docker run -p 8000:8000 kairos-binance`.

## Connect to ChatGPT

Deploy the service behind HTTPS, ideally with access restrictions at ingress. The MCP endpoint is the **server endpoint** (typically `/mcp`), not Binance's `/api/v3/klines` endpoint. Create a private ChatGPT plugin pointing to the deployed HTTPS MCP URL. This source archive itself does not deploy or connect the service. Verify tool discovery and tool invocation after connection.

## Important

- Status OK certifies only the integrity/simultaneity of 12 OHLC closes returned by Binance; formal **BSI activation** also needs validated October 5 historical anchors, post-approval baseline registration and high-water-mark state in Kairos.
- If any symbol is absent, inaccessible, or missing the same closed 4H candle, status is `DATA_ERROR`; do not blend Binance Futures, CoinMarketCap, or live ticker prices.
- The tool never submits an order or certifies a user exchange fill.
- Public Binance market data has rate limits; use normal per-4H cadence, not rapid polling.
