# TrazaUNT React 2.0

Aplicación académica local para revisar contrataciones sintéticas. Frontend React con Vite, API FastAPI y SQLite. Esta versión sustituye la interfaz y el servidor anteriores. Las alertas requieren revisión humana.

## Inicio rápido en Windows

1. Instala Python 3.11 o superior con el lanzador `py`.
2. Extrae TODO el ZIP en una carpeta local con permisos de escritura.
3. Haz doble clic en `iniciar.bat`.
4. La primera ejecución instala las dependencias de Python dentro de `.venv` y requiere internet. Después abre el navegador en `http://127.0.0.1:8000`.
5. Mantén abierta la consola. Ctrl+C detiene la aplicación.

Se incluye `frontend/dist`, la aplicación React compilada. **No necesitas instalar Node para ejecutar esta entrega.** Node se utiliza únicamente si vas a modificar, probar o recompilar el frontend. No abras directamente `frontend/dist/index.html`: la aplicación necesita su API.

Si el puerto 8000 está ocupado, cierra la otra instancia y vuelve a iniciar. Si mueves la carpeta y el entorno virtual deja de funcionar, renombra `.venv` y ejecuta de nuevo `iniciar.bat`. El lanzador comprueba que el frontend compilado exista y muestra los errores en consola. También se incluye `iniciar.ps1`.

## Arranque manual

Desde la raíz del proyecto:

```bat
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

En Linux/macOS usa `python3 -m venv .venv` y sustituye `.venv\Scripts\python.exe` por `.venv/bin/python`. También puedes ejecutar `python iniciar.py`.

Abre `http://127.0.0.1:8000`. SQLite y el conjunto sintético se crean automáticamente al arrancar. Usa un único proceso de Uvicorn, sin `--workers`: esta versión mantiene el resultado del análisis en la memoria de ese proceso.

## Funciones disponibles

- Vista general con indicadores y primeras alertas por prioridad.
- Expedientes con búsqueda, filtro por entidad y paginación del servidor.
- Centro de alertas con filtros por estado, severidad y regla.
- Detalle bajo demanda con pagos, evidencia, aportes del score y seis variables de IA.
- Confirmación o descarte con analista, comentario y comprobación de estado esperado.
- Historial persistente y paginado con hora de Lima.
- Exportaciones CSV desde la API y reevaluación que conserva decisiones.
- Matriz de confusión y métricas sintéticas dibujadas por React.
- Menú adaptable, Acerca de, recorrido de demostración y página de límites.

La navegación utiliza rutas hash (`#expedientes/587`, por ejemplo), por lo que recargar un detalle conserva su ubicación.

## Modificar React

Requiere Node 20.19+ en la rama 20, o Node 22.12+ / posterior compatible.

Terminal 1: ejecuta la API en el puerto 8000 con el comando anterior.

Terminal 2:

```bash
cd frontend
npm ci
npm run dev
```

Vite muestra la dirección de desarrollo y redirige `/api` a `http://127.0.0.1:8000`. No se necesita configurar CORS para este modo. La aplicación final sirve frontend y API bajo el mismo origen.

Después de modificar archivos:

```bash
cd frontend
npm run build
```

Reinicia la aplicación y recarga el navegador para usar la nueva compilación. `frontend/package-lock.json` fija el árbol de dependencias de Node.

## Pruebas

Backend y motor:

```bat
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Frontend:

```bash
cd frontend
npm ci
npm test
```

## Estructura

```text
TrazaUNT/
  app.py                 API y servidor del frontend compilado
  iniciar.py             Arranque aislado y apertura del navegador
  iniciar.bat            Doble clic para Windows
  requirements.txt       Dependencias de ejecución de Python
  requirements-dev.txt   Dependencias adicionales de pruebas
  frontend/
    src/                 Componentes React, estilos y cliente HTTP
    public/assets/       Arte original de TrazaUNT
    dist/                Compilación lista para ejecutar
    package.json         Comandos y dependencias React/Vite
    package-lock.json    Versiones resueltas de Node
  db/                    Modelos y acceso a SQLite
  data/                  Generador sintético
  services/              Reglas, IA, score, explicaciones y revisión
  config/reglas.yaml     Configuración editable
  tests/                 Pruebas de motor, base y API
```

## Configuración y límites

Las reglas siguen en `config/reglas.yaml`. R01 conserva la normalización por tokens, sinónimos controlados y ventana optimizada. El análisis es retrospectivo sobre el universo completo y continúa en memoria, aunque los listados y la búsqueda de la interfaz ya se resuelven mediante SQL paginado.

No hay autenticación, roles ni integración institucional. La cabecera de cliente de las escrituras es una barrera frente a envíos web ajenos, no una identidad de usuario. El servidor se configura para escuchar solo en el equipo local. No lo expongas públicamente ni ingreses datos reales. Los scores no son probabilidades de corrupción. Los umbrales son didácticos y necesitan revisión especializada. Claude permanece apagado.

No se incluyen bases de datos, `.env`, entornos virtuales ni `node_modules`. Si necesitas conservar una base sintética anterior, respáldala y coloca su archivo en `data/trazaunt.sqlite3` con ambas versiones detenidas. La inicialización no elimina registros existentes; los índices se agregan sin reconstruir tablas. Las decisiones anteriores permanecen y los resultados se recalculan al arrancar.

Consulta `MIGRACION_REACT.md` y `VALIDACION.md` para arquitectura, endpoints y comprobaciones.
