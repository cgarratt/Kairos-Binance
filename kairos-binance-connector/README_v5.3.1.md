# Kairos MCP v5.3.1 — Confirmación semanal 5L/5R + BOS

## Despliegue Render
Sustituir en `kairos-binance-connector/` los archivos de este ZIP (conservar configuraciones privadas, si existen). Subir a `main` y desplegar en el servicio Render EXISTENTE. No cambiar URL, Dockerfile Path, Root Directory ni permisos.

## Motor
- Descarga velas diarias Spot cerradas desde 2024-04-20.
- Construye semanas UTC de lunes a domingo; omite semanas parciales.
- Pivot semanal: high o low estrictamente superior/inferior a cinco semanas completas a izquierda y derecha. Confirmación al cierre de la quinta semana derecha.
- BOS: cierre semanal POSTERIOR a la confirmación del pivote, debajo del último pivot low semanal protegido para fase bajista y encima del high protegido para fase alcista.
- Solo avanza en orden CH → CL → SH1 → SL1 → SH2 → SL2 → SH3 si la estructura lo soporta. Las proyecciones Fibonacci de 3 puntos siguen condicionadas.
- HYPE: introducir cuatro valores `historical_ch`, `historical_cl`, `historical_ch_date`, `historical_cl_date` certificados externamente. Nunca utilizar automáticamente los 21 días de Binance como CH/CL histórico.
- `confirmed_wave` permanece null porque la confirmación formal de Elliott y del Cycle Low requiere revisión humana. `candidate_wave` representa el próximo estado vigilado.
- Solo lectura: no toca balances, anclas aprobadas ni órdenes.

## Pruebas
`python -m unittest discover -q` (37 tests).

## Validación pendiente
Después de Render Live y el refresh de herramientas, ejecutar `get_kairos_cycle_phase` para los 12 tokens, verificar extremos, pivotes 5L/5R y eventos BOS; clasificaciones no se aprueban automáticamente. No sustituir las ondas anteriores con resultados de la versión anterior.
