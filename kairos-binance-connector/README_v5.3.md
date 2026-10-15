# KAIROS MCP v5.3 — Cycle Phase Engine (experimental)

## Deploy Render / GitHub
Upload the contents of this directory (not the ZIP itself) to `Kairos-Binance/kairos-binance-connector/` on branch `main`. Preserve your service settings: Docker root/build context `kairos-binance-connector`, same URL and `/mcp` route. The Dockerfile copies `cycle_phase.py` and preserves the six previous tools. Watch Render deploy and verify the new 7th tool appears in ChatGPT.

## New MCP tool
`get_kairos_cycle_phase(symbol='BTCUSDT', historical_ch=None, historical_cl=None, historical_ch_date=None, historical_cl_date=None, pivot_radius=3, min_reversal_pct=8)`

### Interpretation
* H4 starts April 20, 2024 UTC.
* CH is highest observed daily high within H4. CL is the lowest daily low STRICTLY AFTER CH; provisional until analyst confirms.
* Wave pivots start after CL and must alternate SH1, SL1, SH2, SL2, SH3.
* Candidate pivot requires 3 earlier and 3 later fully closed daily bars and minimum 8% reversal on both sides; adjust these heuristic parameters by volatility. This is **NOT** a reliable Elliott wave classifier without analyst verification.
* `confirmed_wave` is always null; phases and pivots are algorithmic candidates. Does not auto-promote anchors.
* O2 uses retracements CL->SH1; O3 uses 3-point extensions CL->SH1->SL1; O4 uses retracements SL1->SH2; O5 uses 3-point extensions SL1->SH2->SL2. Targets only computed with observed candidate pivots; no fabricated downstream waves.
* Historic HYPE CH/CL can be supplied together with dates via manual params. Historical visual approximate `$59` / `$20.50` are not preset or certified; fill in correct image anchor dates first. Without manual anchors, Binance short history gives a separate, incomplete H4 estimate.
* Read-only. Never change approved O2-O5 orders, core custody, portfolio balances, or certified anchor tables.

## Validate
Run `python -m unittest discover -p 'test_*.py'` in connector root. Then `get_kairos_cycle_phase(symbol='BTCUSDT')` and manually review H4 cycle peak, subsequent minimum and candidate pivot sequence. Empty pivots can be correct if CL too recent.

## Operational limitations
This is a conservative exploratory algorithm, not a weekly structural confirmation system. CH/CL computed from absolute window extrema, which may change while H4 is open; short Binance listing history can miss true CH/CL; three-day pivot confirmation can be noisy. Use historical verified anchas and explicit analyst approval before trading decisions.
