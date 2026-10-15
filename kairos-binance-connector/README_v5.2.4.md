# Kairos MCP v5.2.4 — Limited History Macro Fibo

Actualización incremental sobre v5.2.3 para GitHub/Render.

## Archivos a reemplazar
- `macro_fibo.py`
- `test_macro_fibo.py`

No cambiar `server.py`, `Dockerfile`, `market_data.py`, ni las otras cinco herramientas. Mantener la misma URL `/mcp` en Render.

## Política
- `20–59` velas 1D cerradas: `history_mode=LIMITED_HISTORY`, `reliability=LOW`.
- `>=60` velas: `history_mode=FULL_HISTORY`, `reliability=PROVISIONAL`.
- `<20` velas: `DATA_ERROR`.
- Son necesarias >=5 velas cerradas estrictamente posteriores al máximo del ciclo para calcular SL provisional y Fibonacci. Si faltan, devuelve `status=OK`, `cycle_status=INSUFFICIENT_POST_CYCLE_PEAK_HISTORY` y niveles nulos.
- La fecha de ciclo configurada (`2023-01-01` por defecto) nunca se antepone artificialmente al inicio real del listing; `effective_cycle_start_date` indica la primera vela evaluada.
- ATH y ATL son observados solo dentro de Binance Spot, no necesariamente globales. SL y Fibonacci siguen exploratorios, sin efectos sobre posiciones, O2–O5 ni órdenes.

## Validación
`python -m unittest discover -p 'test_*.py'`

Después de commit y Live en Render, ejecutar `get_kairos_macro_fibo(symbol="HYPEUSDT")`; no asegurar éxito hasta probar el historial real. Si la fuente Spot dispone de menos de 20 velas, o no existen >=5 posteriores al peak, el resultado mostrará la limitación explícitamente.
