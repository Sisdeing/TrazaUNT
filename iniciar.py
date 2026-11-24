"""Arranque local de la API y del frontend React ya compilado."""
import hashlib
import os
from pathlib import Path
import socket
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
        print('Instalando dependencias de Python. Primera ejecución con internet...',flush=True)
        subprocess.run([str(python),'-m','pip','install','-r',str(requisitos)],check=True,cwd=raiz)
        marca.write_text(firma)
    with socket.socket() as comprobador:
        try:
            comprobador.bind(('127.0.0.1',8000))
        except OSError as error:
            raise RuntimeError('El puerto 8000 está ocupado. Cierra la otra instancia de TrazaUNT antes de iniciar.') from error
    proceso = subprocess.Popen([str(python),'-m','uvicorn','app:app','--host','127.0.0.1','--port','8000'],cwd=raiz)
    try:
        for _ in range(120):
            if proceso.poll() is not None:
                raise RuntimeError('El servidor no pudo iniciar. Revisa el mensaje anterior.')
            try:
                with urllib.request.urlopen('http://127.0.0.1:8000/api/salud',timeout=.5) as respuesta:
                    if respuesta.status == 200:
                        print('TrazaUNT: http://127.0.0.1:8000 — Ctrl+C para detener.',flush=True)
                        webbrowser.open('http://127.0.0.1:8000')
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
