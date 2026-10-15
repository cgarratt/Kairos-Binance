# KAIROS MCP v5.2.2 — ATL vs SL posterior al ATH

Subir a `kairos-binance-connector/` del repositorio existente estos tres archivos:
- `macro_fibo.py` (reemplazar)
- `server.py` (reemplazar, se mantienen las 6 tools)
- `test_macro_fibo.py` (reemplazar)

No cambiar Dockerfile, URL MCP ni ajustes Render. Desplegar ultimo commit y refrescar herramientas ChatGPT si corresponde.

Campos: `observed_atl` = minimo de todo el historial Binance disponible; `observed_ath` = maximo de todo el historial; `swing_low_post_ath` = minimo de las velas cerradas posteriores al ATH (provisional, no confirmado); `retracement_from_high` = niveles teoricos del rango ATH -> minimo posterior. Si ATH es la ultima vela, no se entrega un SL ni niveles. `swing_low_date` manual debe ser POSTERIOR al ATH.

CUIDADO: el ultimo minimo post-ATH NO es necesariamente un final de bear market; los niveles siguen siendo EXPLORATORY_ONLY. Ninguna modificación automatica a O2-O5, anclas aprobadas ni ordenes. ATH/ATL observados en Binance pueden diferir de otros exchanges.

Ejecutar en el directorio del conector: `python -m unittest discover -p 'test_*.py'`.
