"""Genera y verifica sellos externos de los registros de auditoría SQLite."""

import argparse
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

TABLAS = ("bitacora", "auditoria_api", "eventos_convocatoria")


def codificar(valor):
    return json.dumps(valor, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("ascii")


def medir(base, sello=None):
    datos = {}
    with closing(sqlite3.connect(base.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("BEGIN")
        for tabla in TABLAS:
            limite = (
                sello[tabla]["ultimo_id"]
                if sello is not None
                else db.execute(f"SELECT COALESCE(MAX(id), 0) FROM {tabla}").fetchone()[0]
            )
            if type(limite) is not int or limite < 0:
                raise ValueError("Límite de registro inválido.")
            filas = db.execute(f"SELECT * FROM {tabla} WHERE id <= ? ORDER BY id", (limite,))
            huella = sha256(codificar([tabla, [col[0] for col in filas.description]]))
            cantidad = 0
            for fila in filas:
                huella.update(b"\n")
                huella.update(codificar(fila))
                cantidad += 1
            datos[tabla] = {"ultimo_id": limite, "filas": cantidad, "sha256": huella.hexdigest()}
    return datos


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operacion", choices=("sellar", "verificar"))
    parser.add_argument("base", type=Path)
    parser.add_argument("sello", type=Path)
    args = parser.parse_args()
    try:
        if args.operacion == "sellar":
            sello = {"version": 1, "tablas": medir(args.base)}
            with args.sello.open("x", encoding="utf8") as destino:
                json.dump(sello, destino, indent=2)
            print("Sello generado. Conserve la copia bajo custodia independiente.")
            return 0
        sello = json.loads(args.sello.read_text(encoding="utf8"))
        if sello["version"] != 1 or set(sello["tablas"]) != set(TABLAS):
            raise ValueError("Formato de sello desconocido.")
        actual = medir(args.base, sello["tablas"])
        discrepancias = [tabla for tabla in TABLAS if actual[tabla] != sello["tablas"][tabla]]
        if discrepancias:
            print("Discrepancias en: " + ", ".join(discrepancias))
            return 1
        print("Los registros del corte coinciden con el sello.")
        return 0
    except (OSError, ValueError, sqlite3.Error, KeyError, TypeError) as error:
        print(f"Verificación o sellado interrumpido: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
