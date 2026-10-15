# Kairos MCP v5.2.3 — Cycle High independiente del ATH

Cambios: `observed_ath` y `observed_atl` en historial consultado; `cycle_peak` es el HIGH mayor desde `cycle_start_date` (por defecto `2023-01-01`); `swing_low_post_cycle_peak` es el LOW diario mínimo estrictamente posterior a `cycle_peak`. Los retrocesos descendentes usan `cycle_peak` y el mínimo provisional posterior. La clave heredada `swing_low_post_ath` sigue disponible como alias DEPRECATED y ya no significa post-ATH histórico; usar `swing_low_post_cycle_peak`.

Fecha de inicio del ciclo es una hipótesis ajustable; no se detecta automáticamente con certeza. Un token listado más recientemente usa su historial disponible. Para otros ciclos pasar `cycle_start_date=YYYY-MM-DD`.

Actualización del repo `cgarratt/Kairos-Binance`, carpeta `kairos-binance-connector`: reemplazar `macro_fibo.py`, `server.py`, `test_macro_fibo.py`. No cambiar Dockerfile. Confirmar Live en Render y refrescar herramientas MCP para que el nuevo parámetro sea visible.

Prueba: `python -m unittest test_macro_fibo -v`. Sin modificación de anclas certificadas, O2–O5, órdenes o custodia. Sólo lectura.
