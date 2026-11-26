"""Administración de cuentas por el operador local."""

import argparse
from getpass import getpass

from app import (
    crear_app,
)  # Registra el esquema completo antes de comprobar una base existente.
from db.database import crear_motor, crear_tablas
from services.seguridad import ROLES, guardar_cuenta


def main():
    parser = argparse.ArgumentParser(
        description="Crear o actualizar una cuenta local con el servidor detenido."
    )
    parser.add_argument("usuario")
    parser.add_argument("rol", choices=ROLES)
    parser.add_argument("nombre")
    parser.add_argument("--ruc", help="Obligatorio para el rol empresa: RUC del proveedor vinculado.")
    args = parser.parse_args()
    clave = getpass("Contraseña (12 caracteres como mínimo): ")
    if clave != getpass("Repetir contraseña: "):
        parser.error("Las contraseñas no coinciden.")
    motor = crear_motor()
    try:
        crear_tablas(motor)
        guardar_cuenta(motor, args.usuario, args.nombre, args.rol, clave, args.ruc)
    finally:
        motor.dispose()


if __name__ == "__main__":
    main()
