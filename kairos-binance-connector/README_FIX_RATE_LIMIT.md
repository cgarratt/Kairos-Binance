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

## Corrección de empaquetado v2
Dockerfile incluye binance_http.py en COPY. El paquete inicial omitía copiar ese módulo a /app y fallaba al arrancar. Reemplazar también Dockerfile y volver a desplegar.

## Release MCP v5.3.3 · 2026-11-01
- Logs binance_request: tool, path, symbol, interval, limit, http_status, used_weight, retry_after, cache y duración. used_weight vacío significa que Binance no lo informó, NO consumo cero. No se registran URLs completas, credenciales ni cuerpos de error.
- audited_tool conserva la firma de las herramientas MCP y atribuye sus consultas internas.
- Caché SQLite compartida de klines; páginas totalmente cerradas con endTime anterior al comienzo de la vela vigente se reutilizan hasta 30 días. Otras consultas klines expiran al siguiente cierre del intervalo. Los consumidores mantienen su filtrado closed-only. Máximo 256 respuestas; valores Spot no entran aquí.
- Caché válida de históricos puede atenderse durante una pausa; no se realizan nuevas llamadas para ello. No habilita valoración Spot ni operaciones con datos vencidos.
- Mantener BINANCE_GUARD_DB en disco persistente si se necesita conservar pausa/caché entre redeploys. El almacenamiento /tmp predeterminado no garantiza esa persistencia. Solo un proceso/worker para el control de concurrencia por proceso.
- 55 pruebas locales (52 principales + 3 históricas) aprobadas. Dockerfile/importaciones de server.py verificadas con archivos copiados según COPY; no se construyó una imagen Docker real ni se desplegó producción.
- No se identifica IP pública ni consumidor externo mediante estos logs: permiten ver el consumo informado para la IP y las solicitudes locales. Esa limitación evita atribuir tráfico de otros clientes a Kairos sin evidencia.
