"""Importación selectiva del padrón empresarial local, separada de los expedientes demo."""

import argparse
import csv
from contextlib import closing
from datetime import date
import io
from pathlib import Path
import re
import sqlite3
import unicodedata

RUTA_PADRON = Path(__file__).resolve().parents[1] / "data" / "real" / "padron.sqlite3"
ORIGEN = "https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html"


def ruc_valido(ruc, demo=False):
    if not re.fullmatch(r"[0-9]{11}", ruc):
        return False
    if ruc.startswith("00"):
        return demo
    if ruc[:2] not in {"10", "15", "16", "17", "20"}:
        return False
    total = sum(
        int(n) * peso for n, peso in zip(ruc[:10], (5, 4, 3, 2, 7, 6, 5, 4, 3, 2))
    )
    return int(ruc[-1]) == (11 - total % 11) % 10


def normalizar(texto):
    sin_tildes = unicodedata.normalize("NFKD", texto.strip().upper())
    return re.sub(r"[^A-Z0-9]", "", sin_tildes)


def importar(archivo, destino, rucs, corte):
    if not rucs or any(not r.startswith("20") or not ruc_valido(r) for r in rucs):
        raise ValueError("Seleccione exclusivamente RUC válidos de personas jurídicas.")
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(archivo, "rb") as crudo:
        muestra = crudo.read(8192)
        try:
            muestra.decode("utf-8-sig")
            codificacion = "utf-8-sig"
        except UnicodeDecodeError:
            codificacion = "latin1"
        crudo.seek(0)
        entrada = io.TextIOWrapper(crudo, encoding=codificacion, newline="")
        cabecera = entrada.readline()
        separador = max("|;,\t", key=cabecera.count)
        columnas = [
            normalizar(x) for x in next(csv.reader([cabecera], delimiter=separador))
        ]
        opciones = [
            ("RUC",),
            ("NOMBREORAZONSOCIAL", "RAZONSOCIAL"),
            ("ESTADODELCONTRIBUYENTE", "ESTADOCONTRIBUYENTE"),
            (
                "CONDICIONDEDOMICILIO",
                "CONDICIONDELDOMICILIO",
                "CONDICIONDELDOMICILIOFISCAL",
                "CONDICIONDOMICILIO",
            ),
        ]
        indices = []
        for grupo in opciones:
            idx = next(
                (columnas.index(nombre) for nombre in grupo if nombre in columnas), None
            )
            if idx is None:
                raise ValueError(
                    "El padrón no contiene todas las columnas registrales requeridas."
                )
            indices.append(idx)
        with closing(sqlite3.connect(destino)) as con, con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS padron(ruc TEXT PRIMARY KEY, razon_social TEXT NOT NULL, estado TEXT NOT NULL, condicion TEXT NOT NULL, corte TEXT NOT NULL)"
            )
            leidos = set()
            for fila in csv.reader(entrada, delimiter=separador):
                if len(fila) <= max(indices):
                    continue
                ruc, nombre, estado, condicion = [fila[i].strip() for i in indices]
                if ruc in rucs:
                    if ruc in leidos:
                        raise ValueError("RUC duplicado en el archivo de origen.")
                    con.execute(
                        """INSERT INTO padron VALUES (?,?,?,?,?) ON CONFLICT(ruc) DO UPDATE SET
                                razon_social=excluded.razon_social, estado=excluded.estado, condicion=excluded.condicion,
                                corte=excluded.corte WHERE excluded.corte >= padron.corte""",
                        (ruc, nombre, estado, condicion, corte.isoformat()),
                    )
                    leidos.add(ruc)
            return len(leidos)


def consultar_publico(ruc, ruta=RUTA_PADRON):
    if not ruc.startswith("20") or not ruc_valido(ruc):
        raise ValueError(
            "Sólo se admiten RUC válidos de personas jurídicas en el padrón público."
        )
    datos = None
    if ruta.is_file():
        with closing(sqlite3.connect(ruta.as_uri() + "?mode=ro", uri=True)) as con:
            con.row_factory = sqlite3.Row
            fila = con.execute(
                "SELECT ruc,razon_social,estado,condicion,corte FROM padron WHERE ruc=?",
                (ruc,),
            ).fetchone()
            datos = dict(fila) if fila else None
    return dict(
        ruc=ruc,
        origen="real_publico",
        fuente=ORIGEN,
        registro=datos,
        ifp=None,
        estado="Registro localizado" if datos else "No evaluado",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Importa RUC empresariales seleccionados desde un padrón SUNAT descomprimido."
    )
    parser.add_argument("archivo", type=Path)
    parser.add_argument("--ruc", required=True, action="append")
    parser.add_argument("--corte", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    print(
        f"Registros localizados: {importar(args.archivo, RUTA_PADRON, set(args.ruc), args.corte)}"
    )
