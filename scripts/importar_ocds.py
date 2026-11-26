"""Uso: python scripts/importar_ocds.py archivo.jsonl.gz"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from services.datos_publicos import importar, desde_ocds
from db.database import crear_motor, crear_tablas
from app import crear_app  # registra todos los modelos
if __name__=='__main__':
    if len(sys.argv)!=2: sys.exit('Uso: python scripts/importar_ocds.py archivo.jsonl.gz')
    motor=crear_motor();crear_tablas(motor)
    try: print('Expedientes públicos nuevos:', importar(motor, desde_ocds(sys.argv[1])))
    finally: motor.dispose()
