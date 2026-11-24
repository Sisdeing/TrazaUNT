# Migración a React

## Arquitectura entregada

React ejecuta los componentes y la navegación en el navegador. FastAPI recibe peticiones HTTP, valida revisiones y consulta SQLite mediante SQLAlchemy. El motor Python mantiene las seis reglas y Isolation Forest con seis variables operativas. Uvicorn sirve la API y los archivos compilados de React. No existe iframe, postMessage ni dependencia del framework de interfaz anterior.

Los listados utilizan filtros SQL, COUNT, LIMIT y OFFSET. La API devuelve un máximo de 100 registros por página y 25 por defecto. La evidencia completa, pagos y variables se solicitan únicamente al abrir un expediente. Resumen y métricas exponen agregados, no el universo completo ni etiquetas individuales. El análisis sigue siendo una operación de conjunto completo y el resultado se conserva en memoria en un solo proceso. La exportación completa puede consumir memoria adicional y no es una descarga paginada.

Se conservan WAL, busy_timeout y BEGIN IMMEDIATE. Un lock del proceso serializa el reanálisis y las revisiones y protege el resultado en memoria. La comprobación de estado esperado impide sobrescribir una decisión obsoleta. Esto no sustituye autenticación ni garantiza escalabilidad multiusuario institucional.

## Endpoints principales

| Método | Ruta | Uso |
|---|---|---|
| GET | /api/salud | Estado local |
| GET | /api/configuracion | Entidades y nombres de reglas |
| GET | /api/resumen | Indicadores y primeras seis alertas |
| GET | /api/expedientes | Búsqueda, entidad y página |
| GET | /api/expedientes/{id} | Detalle, evidencia y movimientos |
| GET | /api/alertas | Filtros y página de alertas vigentes |
| POST | /api/alertas/{id}/revision | Decisión, analista, comentario y estado esperado |
| POST | /api/analisis | Recalcular conservando decisiones |
| GET | /api/historial | Movimientos paginados |
| GET | /api/metricas | Métricas sintéticas agregadas |
| GET | /api/exportar/alertas | CSV de todas las alertas |
| GET | /api/exportar/historial | CSV de bitácora |

Las escrituras llevan `X-Traza-Client: react`. Los conflictos de revisión devuelven HTTP 409 y los problemas operativos de SQLite devuelven 503. Los datos de formulario se validan en el servidor. React conserva el comentario cuando ocurre un error para permitir corregirlo. Los CSV escapan contenido que podría interpretarse como fórmula. Swagger está disponible en `/api/docs`; para probar escrituras desde otras herramientas hay que enviar la cabecera de cliente.

## Qué sigue pendiente

- Identidad corporativa, roles y permisos.
- Protección criptográfica de la bitácora con anclajes externos. Una cadena de hashes sola puede reescribirse si el atacante controla todos los registros.
- Conectores institucionales autorizados y verificados, procesos por lotes y PostgreSQL cuando el volumen/concurrencia lo justifique.
- Un análisis en segundo plano con trabajos y caché compartida antes de activar múltiples procesos.
- Evaluación de desempeño sobre escenarios independientes y de la utilidad adicional de las features de IA. Las decisiones de confirmar una alerta no equivalen automáticamente a etiquetas de fraude.

## Documentación de referencia

- React: https://react.dev/learn/build-a-react-app-from-scratch
- Vite: https://vite.dev/guide/build
- FastAPI, ciclo de vida: https://fastapi.tiangolo.com/advanced/events/
- FastAPI, pruebas: https://fastapi.tiangolo.com/advanced/testing-events/
