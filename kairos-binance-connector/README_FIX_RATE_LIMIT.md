# Kairos Binance MCP — protección HTTP 418/429 (2026-10-31)

Base: repositorio cgarratt/Kairos-Binance, rama main. Cambios limitados a kairos-binance-connector; no modifica MASTER, KairosWeb ni reglas de trading.

## Instalar
1. Descomprimir el paquete. Reemplazar el contenido de kairos-binance-connector en el mismo directorio del repositorio GitHub. No subir el ZIP como único archivo.
2. El archivo NUEVO binance_http.py es obligatorio; market_data.py y market_intelligence.py lo importan.
3. Desplegar el commit en Render en el servicio MCP Binance existente. Conservar server.py, Dockerfile y variables actuales. No se añaden dependencias.
4. Usar UN proceso/worker: la serialización y la caché son por proceso. Una pausa se guarda en SQLite para compartirla entre los consumidores que usen el mismo archivo.
5. Opcional: configurar BINANCE_GUARD_DB con una ruta absoluta sobre un disco persistente y escribible (ejemplo /var/data/kairos-binance-guard.sqlite3). Por defecto /tmp/kairos-binance-guard.sqlite3 sobrevive a reiniciar el proceso si conserva el filesystem, pero NO se garantiza persistencia ante un redeploy o sustitución del contenedor. La carpeta debe existir. No borrar el archivo para saltarse una pausa.
6. Durante una pausa, DATA_ERROR y records vacíos son el comportamiento esperado. La respuesta Spot incorpora http_status, retry_at_utc y retry_after_seconds. Los logs registran Binance cooldown sin credenciales. KairosWeb 3.0.29 puede seguir mostrando un error genérico; este paquete no cambia la interfaz Web.
7. Al vencer el plazo, probar Spot una sola vez. Revisar que vuelva status OK y que la hora de observación sea reciente. No se ha hecho escritura remota ni prueba de producción al preparar este paquete.

## Qué cambia
- Todas las consultas HTTP de Spot, OHLCV, indicadores, libro, BSI, macro y ciclo pasan por el mismo guardián.
- Una sola consulta de red simultánea por proceso, separación mínima 300 ms y espera de cola limitada a dos segundos. Cola ocupada devuelve error en lugar de acumular llamadas indefinidamente.
- HTTP 418/429: no reintenta inmediatamente ni cambia de host/IP. Respeta Retry-After numérico/fecha y el timestamp banned until si llega en el cuerpo. Se usa el plazo mayor.
- Si Binance no entrega vencimiento, aplica pausa LOCAL conservadora de 15 minutos (418) o 60 segundos (429). NO significa que Binance vaya a desbloquear exactamente a esa hora; una respuesta posterior puede prolongar la pausa.
- Spot válido se reutiliza hasta cinco segundos para el mismo conjunto de símbolos, manteniendo la hora original. Las respuestas fallidas no se convierten en precios ni se sirve una observación vencida para ocultar fallos.
- No demuestra qué consumidor generó el exceso original. Otros servicios o usuarios de la misma IP pueden seguir agotando la cuota. Controlar esos consumidores también; no hay garantía absoluta de evitar futuros bloqueos.

## Verificación local
python -m unittest discover -q  # 49 pruebas
python -m unittest discover -s tests -q  # 3 pruebas históricas adicionales
Incluye concurrencia, persistencia, vencimientos, caché sin rejuvenecer timestamps y conservación de módulos existentes. Transporte simulado: sin consulta real a Binance durante las pruebas. No se instaló en Render ni se publicó en GitHub.
