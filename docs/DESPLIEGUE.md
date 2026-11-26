# Instalación, operación y recuperación

## Windows

Extrae el ZIP completo. El directorio raíz contiene iniciar.bat, iniciar.py, frontend/dist y data/demo. Ejecuta iniciar.bat o `py -3 iniciar.py`. El primer arranque crea .venv e instala requirements.txt. En el ZIP se incluye offline/win-amd64-cp314, que permite instalar sin red con Python 3.14 de 64 bits en Windows x64. El lanzador selecciona el directorio según el intérprete del entorno virtual. En otras plataformas se utiliza el índice de paquetes. El navegador abre el resumen ejecutivo con una sesión local. Si el puerto 8000 está ocupado, cierra la instancia anterior o inicia manualmente en otro puerto. Evita abrir el archivo HTML directamente.

Para una **nueva demostración independiente**, detén la instancia actual y ejecuta `py -3 iniciar.py --nueva-demo`. El lanzador conserva el archivo anterior y crea uno nuevo en data/sesiones-demo. Reabrir con iniciar.bat usa la base predeterminada data/trazaunt.sqlite3. El ZIP incluye una base inicial exclusivamente sintética.

## Cuentas y arranque manual

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m scripts.cuenta analista1 analista "Analista de integridad"
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Introduce una contraseña local de al menos 12 caracteres en el prompt. Luego inicia sesión en http://127.0.0.1:8000. Los roles disponibles son administrador, analista y auditor (perfil Universidad) y empresa, que requiere `--ruc` del proveedor vinculado. El rol consulta se conserva por compatibilidad y solo ve el Inicio. Detén el servicio al actualizar cuentas para invalidar las sesiones en memoria. En Linux usa python3 y .venv/bin/python.

La API lee DATABASE_URL del entorno del proceso, con formato SQLite en archivo. En PowerShell, por ejemplo, usa `$env:DATABASE_URL='sqlite:///data/otra-demo.sqlite3'` antes de ejecutar los comandos. .env.example enumera la configuración. El servicio usa un proceso. Para consultar OpenAPI descarga /api/openapi.json en una sesión de analista. La interfaz Swagger de FastAPI puede requerir recursos externos.

## Docker

```sh
docker compose build
docker compose up -d
docker compose exec trazaunt python -m scripts.cuenta analista1 analista "Analista de integridad"
docker compose ps
```

Abre http://127.0.0.1:8000 con esa cuenta. El contenedor utiliza usuario sin privilegios, un volumen para persistencia y comprobación GET /api/health. `docker compose down` detiene la demo y conserva el volumen. Las dependencias y la imagen base requieren red durante la construcción. La imagen utiliza el frontend ya compilado. Docker no estaba instalado en el equipo de validación.

## Modificar o probar

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run build
```

Vite requiere Node 20.19+ o 22.12+ compatible. El servidor de desarrollo redirige /api a 127.0.0.1:8000. Para el E2E opcional instala playwright en el entorno y ejecuta scripts/validar_navegador.py con `--chromium` y la ruta del ejecutable de Microsoft Edge o Chromium. Sin esa opción necesita Chromium instalado mediante el instalador de Playwright.

Respalda la carpeta data con el servidor detenido. Para recuperar la demo limpia también puedes extraer el ZIP en una carpeta nueva. Antes de distribuir una copia, usa una base generada de nuevo y excluye data/real, bases de trabajo, secretos y entornos virtuales.
