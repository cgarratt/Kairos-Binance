# Kairos MCP v5.2 — Sexta herramienta Fibo Macro

Nueva función `get_kairos_macro_fibo(symbol='BTCUSDT', start_date=None, end_date=None, swing_low_date=None)`.

- Datos **únicamente** de `Binance Spot /api/v3/klines`, velas **1d cerradas**. Paginación `startTime/endTime` hasta 1.000 velas por lote (tope 16 lotes y abortar ante gaps).
- Selecciona el máximo HIGH diario observado (ATH de cobertura Binance, **no** ATH global certificado).
- Por defecto usa el mínimo LOW **anterior al máximo observado**, como **candidato exploratorio**, NO como Swing Low macro del último ciclo bajista certificado.
- Se puede indicar `swing_low_date='YYYY-MM-DD'` para comprobar un ancla elegida previamente, siempre anterior al máximo.
- Entrega Fibonacci de retroceso medido **desde máximo hacia mínimo**: 23.6%, 38.2%, 50%, 61.8%, 78.6%.
- No actualiza O2/O3/O4/O5, libro de órdenes, patrimonio ni anclas aprobadas; confirmar diferencias frente a TradingView de forma explícita.
- No requiere credenciales, solo lectura. A causa de la descarga histórica, la primera consulta puede tardar y consumir más peso/cuota de Binance.

## Render existente
Repositorio `cgarratt/Kairos-Binance`; carpeta `kairos-binance-connector`.
1. Subir o sustituir `server.py`, `Dockerfile` y agregar `macro_fibo.py`, `test_macro_fibo.py` en la carpeta existente.
2. Conservar `market_data.py`, `market_intelligence.py`, `requirements.txt` (esta entrega incluye copias compatibles).
3. Dejar sin cambios Root Directory, Dockerfile Path, Docker Build Context y URL del servicio Render.
4. Lanzar `Deploy latest commit` (o esperar auto-deploy) y comprobar Live; verificar que ChatGPT descubra **6 herramientas**, no únicamente BSI.
5. Pruebas locales: `python -m unittest discover -p 'test_*.py'` (18 pruebas realizadas, sin acceso a producción).

Ejemplo: `get_kairos_macro_fibo(symbol='BTCUSDT')`

**Aviso:** Esta herramienta **no identifica de manera definitiva** un último ciclo bajista ni su Swing Low: eso requiere reglas de segmentación del ciclo, confirmación humana y posible historia pre-Binance.
