# MCP_Binance v5.4.1 · Suite 2026.11.02.1

Release coordinado con Web3.0.33 y GPT1.3.16. Herramienta local de versión: get_kairos_binance_service_info(). No hace consultas de mercado. El resto de herramientas y sus alcances se conservan. Revisar INSTALACION_SUITE.md del paquete completo. Preparado localmente; no desplegado ni certificado contra el servidor remoto.

# Kairos Binance MCP v5.4.0 — Carga manual conjunta

Nueva herramienta get_kairos_dashboard_snapshot: precios/bid/ask de12 pares, hasta999 velas diarias cerradas por par, indicadores diarios y ciclo. Se calcula cada sección a partir de los mismos históricos, sin solicitudes separadas para indicadores/ciclo. Lecturas REST no atómicas.

La primera carga necesita hasta14 solicitudes Binance, no una sola solicitud REST:2 lotes de cotizaciones y12 históricos diarios. Los históricos válidos permanecen en la caché SQLite de binance_http hasta el siguiente cierre UTC. La caché completa/Spot dura60 segundos conservando la fecha original. Una restricción418/429 cancela la carga y respeta Retry-After; no se publica una carga parcialmente bloqueada.

KairosWeb v3.0.31 invoca esta herramienta únicamente desde Actualizar Spot. Navegación, estado y diagnósticos Web usan el snapshot local. No se descargan históricos intradía que Web no utiliza. Las herramientas anteriores siguen disponibles para clientes independientes y Alertas. No hay planificador interno ni cambio de la automatización horaria :15.

Instalar TODO este directorio en kairos-binance-connector, incluyendo dashboard_snapshot.py y el Dockerfile actualizado. Mantener el endpoint /mcp y variables existentes. Un worker. Instalar antes de Web3.0.31; no hay fallback a llamadas antiguas.

BINANCE_GUARD_DB puede apuntar a un disco persistente escribible; /tmp se puede perder en Render Free. Este release no configura almacenamiento externo ni cambia la IP de salida. No garantiza desbloqueo.

Pruebas locales:55 unittest en raíz +3 en tests. La copia de módulos de Docker/importación está verificada; Docker real y despliegue remoto pendientes. Sin llamadas live a Binance durante las pruebas, sin credenciales de cuenta ni operaciones financieras.

## Documentación anterior

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
