"""Arranque local de la API y del frontend React ya compilado."""
import argparse
import hashlib
from datetime import datetime
from uuid import uuid4
import os
from pathlib import Path
import socket
import secrets
import subprocess
import sys
import time
import urllib.request
import venv
import webbrowser


def main():
    if sys.version_info < (3, 11):
        raise RuntimeError('Instala Python 3.11 o superior.')
    raiz = Path(__file__).resolve().parent
    if not (raiz / 'frontend/dist/index.html').is_file():
        raise RuntimeError('Falta frontend/dist. En frontend ejecuta npm ci y npm run build con Node 20.19+ o 22.12+.')
    entorno = raiz / '.venv'
    python = entorno / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.is_file():
        print('Creando entorno virtual local...', flush=True)
        venv.EnvBuilder(with_pip=True).create(entorno)
    subprocess.run([str(python),'-c','import sys; assert sys.version_info >= (3,11), "Renombra .venv y crea un entorno con Python 3.11+"'],check=True,cwd=raiz)
    requisitos = raiz / 'requirements.txt'
    firma = hashlib.sha256(requisitos.read_bytes()).hexdigest()
    marca = entorno / '.requisitos.sha256'
    if not marca.exists() or marca.read_text() != firma:
        plataforma = subprocess.check_output([str(python),'-c',
            "import sys,sysconfig; print(sysconfig.get_platform()+'-cp'+str(sys.version_info.major)+str(sys.version_info.minor))"],
            text=True,cwd=raiz).strip()
        paquetes = raiz / "offline" / plataforma
        opciones = ["--no-index","--find-links",str(paquetes)] if paquetes.is_dir() else []
        print("Instalando dependencias desde el paquete local..." if opciones else
              "Instalando dependencias de Python desde el índice de paquetes...",flush=True)
        subprocess.run([str(python),'-m','pip','install',*opciones,'-r',str(requisitos)],check=True,cwd=raiz)
        marca.write_text(firma)
    with socket.socket() as comprobador:
        try:
            comprobador.bind(('127.0.0.1',8000))
        except OSError as error:
            raise RuntimeError('El puerto 8000 está ocupado. Cierra la otra instancia de TrazaUNT antes de iniciar.') from error
    parser = argparse.ArgumentParser(description="Abrir la demostración local de TrazaUNT.")
    parser.add_argument("--nueva-demo", action="store_true", help="Crear una base sintética independiente.")
    args = parser.parse_args()
    acceso = secrets.token_urlsafe(32)
    entorno_servidor = {**os.environ, 'TRAZA_ACCESO_LOCAL': acceso}
    if args.nueva_demo:
        carpeta = raiz / "data" / "sesiones-demo"
        carpeta.mkdir(parents=True,exist_ok=True)
        ruta = carpeta / f"demo-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}.sqlite3"
        entorno_servidor["DATABASE_URL"] = "sqlite:///" + ruta.as_posix()
        print(f"Nueva base sintética: {ruta}",flush=True)
    proceso = subprocess.Popen([str(python),'-m','uvicorn','app:app','--host','127.0.0.1','--port','8000'],cwd=raiz,env=entorno_servidor)
    try:
        for _ in range(120):
            if proceso.poll() is not None:
                raise RuntimeError('El servidor no pudo iniciar. Revisa el mensaje anterior.')
            try:
                with urllib.request.urlopen('http://127.0.0.1:8000/api/salud',timeout=.5) as respuesta:
                    if respuesta.status == 200:
                        print('TrazaUNT: http://127.0.0.1:8000 — Ctrl+C para detener.',flush=True)
                        destino = ('/#acceso=' + acceso if os.getenv('TRAZA_ENTORNO', 'demo') == 'demo'
                                   else '/?vista=equipo')
                        webbrowser.open('http://127.0.0.1:8000' + destino)
                        break
            except OSError:
                time.sleep(.5)
        else:
            raise RuntimeError('El servidor tardó demasiado en iniciar. Revisa la consola y vuelve a intentar.')
        proceso.wait()
    finally:
        if proceso.poll() is None:
            proceso.terminate()
            try: proceso.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proceso.kill();proceso.wait()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Aplicación detenida.')
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f'No se pudo iniciar TrazaUNT: {error}',file=sys.stderr)
        sys.exit(1)
