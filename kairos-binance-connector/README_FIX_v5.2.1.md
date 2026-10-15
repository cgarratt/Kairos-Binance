# Kairos Binance MCP v5.2.1 — Macro Fibo hotfix

Subir al directorio existente `kairos-binance-connector/` de GitHub.

Archivos que deben reemplazarse: `macro_fibo.py`, `test_macro_fibo.py`.

No cambiar server.py, Dockerfile, market_data.py, market_intelligence.py ni configuraciones de Render.

Corrección: validar metadata `closeTime` dentro del mismo día UTC, sin exigir milisegundo exacto; verificar apertura UTC, integridad temporal y precios; mensajes de error fechados.

Pruebas locales: `python -m unittest discover -p "test_*.py"` — 21 OK.

IMPORTANTE: la causa específica en Binance producción aún no se pudo confirmar. Ejecutar `get_kairos_macro_fibo` sobre BTC después de desplegar; si retorna DATA_ERROR, compartir su nuevo `reason` para aislar el registro real. No actualiza anclas aprobadas.
