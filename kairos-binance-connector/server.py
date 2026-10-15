"""Read-only MCP endpoint for ChatGPT. Deploy behind HTTPS with network egress to Binance."""
from fastmcp import FastMCP
from market_data import synchronized_snapshot

mcp = FastMCP("Kairos Binance Market Data")

@mcp.tool()
def get_kairos_bsi_4h_closes() -> dict:
    """Get last fully closed UTC-aligned 4H Binance Spot close for BTC and 11 Kairos altcoins.

    Returns certifiable=true ONLY when all twelve spot candles share precisely
    the same 4H close timestamp. Never substitutes live ticks, futures, old candles
    or another provider. Read-only. Does not trade or access private accounts.
    """
    return synchronized_snapshot()

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
