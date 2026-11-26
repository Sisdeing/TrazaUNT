"""Carga inicial reproducible. Ejecutar desde la raíz: python -m db.seed."""

import argparse
import json
from pathlib import Path

from sqlalchemy import insert
from sqlalchemy.engine import Engine

from data.generador_sintetico import generar_datos
from db.database import RUTA_BD, contar_registros, crear_motor, crear_tablas, obtener_sesion
from db.models import Contratacion, Entidad, Pago, Proveedor


def poblar_si_vacia(motor: Engine, semilla: int = 42, n_normales: int = 500) -> dict:
    """Carga todo o nada. Repetir la llamada no duplica ni reemplaza registros."""
    crear_tablas(motor)
    with obtener_sesion(motor) as sesion:
        # Serializa la comprobación y carga inicial entre arranques concurrentes de la aplicación.
        sesion.connection().exec_driver_sql("BEGIN IMMEDIATE")
        conteos = contar_registros(sesion)
        if any(conteos.values()):
            return {"creados": False, "conteos": conteos}

        datos = generar_datos(semilla=semilla, n_normales=n_normales)
        # Este orden respeta las referencias entre tablas.
        for modelo in (Entidad, Proveedor, Contratacion, Pago):
            sesion.execute(insert(modelo), datos[modelo.__tablename__])
        return {"creados": True, "conteos": contar_registros(sesion)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Crear una base de datos sintética de TrazaUNT.")
    parser.add_argument("--ruta", type=Path, default=RUTA_BD, help="Archivo SQLite de destino")
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--normales", type=int, default=500)
    args = parser.parse_args()
    motor = crear_motor(args.ruta)
    try:
        resultado = poblar_si_vacia(motor, args.semilla, args.normales)
        print("Base:", args.ruta.resolve())
        print("Datos creados." if resultado["creados"] else "La base ya contiene datos; no se modificó.")
        print(json.dumps(resultado["conteos"], indent=2, ensure_ascii=False))
    finally:
        motor.dispose()


if __name__ == "__main__":
    main()
