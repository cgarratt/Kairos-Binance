"""Kairos Binance public-data MCP, read-only (no account credentials/trading)."""
from fastmcp import FastMCP
from market_data import synchronized_snapshot
from market_intelligence import spot_prices, ohlcv, indicators, orderbook
from macro_fibo import macro_fibo
from cycle_phase import cycle_phase

mcp = FastMCP('Kairos Binance Market Data')

@mcp.tool()
def get_kairos_bsi_4h_closes() -> dict:
    """Get fully closed, UTC-aligned Binance Spot 4H closes for all 12 tokens; certify only if synchronized."""
    return synchronized_snapshot()

@mcp.tool()
def get_kairos_spot_prices(symbols: list[str] | None = None) -> dict:
    """Get live-ish Binance Spot last price and best bid/ask for the 12 Kairos pairs (or an approved subset). Read-only; non-atomic observations."""
    return spot_prices(symbols)

@mcp.tool()
def get_kairos_ohlcv(symbol: str = 'BTCUSDT', interval: str = '4h', limit: int = 200) -> dict:
    """Get closed-only UTC Spot OHLCV candles (15m, 1h, 4h, 1d), max 999. Returns DATA_ERROR on gaps/short history."""
    return ohlcv(symbol, interval, limit)

@mcp.tool()
def get_kairos_indicators(symbol: str = 'BTCUSDT', interval: str = '4h', history: int = 300) -> dict:
    """Compute RSI14 (Wilder), RSI SMA14, Stoch RSI(14,14,3,3) K+D, EMA20/50/100/200 on fully closed Spot candles."""
    return indicators(symbol, interval, history)

@mcp.tool()
def get_kairos_orderbook(symbol: str = 'BTCUSDT', limit: int = 100) -> dict:
    """Get Binance Spot REST orderbook snapshot, spread and depth/imbalance. Public and read-only; not live WebSocket stream."""
    return orderbook(symbol, limit)

@mcp.tool()
def get_kairos_macro_fibo(symbol: str = 'BTCUSDT', start_date: str | None = None,
                         end_date: str | None = None, swing_low_date: str | None = None,
                         cycle_start_date: str = '2023-01-01') -> dict:
    """Read-only Binance Spot daily history with pagination: historical ATH/ATL, selected bull-cycle peak, provisional post-cycle-peak low and Fibonacci ranges.

    YYYY-MM-DD filters; swing_low_date optionally specifies a human-selected low candle strictly AFTER the selected cycle high.
    Output is EXPLORATORY_ONLY and MUST NOT update approved Kairos Fibo Macro, O2-O5 or orders.
    """
    return macro_fibo(symbol, start_date, end_date, swing_low_date, cycle_start_date)

@mcp.tool()
def get_kairos_cycle_phase(symbol: str = 'BTCUSDT', historical_ch: float | None = None,
                           historical_cl: float | None = None,
                           historical_ch_date: str | None = None,
                           historical_cl_date: str | None = None,
                           pivot_radius: int = 5, min_reversal_pct: float = 8) -> dict:
    """Explore H4 using confirmed weekly 5L/5R pivots AND weekly-close BOS; project conditional 3-point Fibonacci.
    Optional four-field human-supplied historical CH/CL for limited-history symbols such as HYPE.
    All results are PROVISIONAL and read-only; do not modify approved anchors/orders.
    """
    return cycle_phase(symbol, historical_ch=historical_ch,historical_cl=historical_cl,
        historical_ch_date=historical_ch_date,historical_cl_date=historical_cl_date,
        pivot_radius=pivot_radius,min_reversal_pct=min_reversal_pct)

if __name__ == '__main__':
    import os
    mcp.run(transport='http', host='0.0.0.0', port=int(os.environ.get('PORT', '10000')))
