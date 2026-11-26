"""Conexión, transacciones y consultas explícitas para no filtrar el ground truth."""

from contextlib import contextmanager
from pathlib import Path
import os
import sqlite3
from contextlib import closing

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import Session

from db.models import Alerta, Base, Bitacora, Contratacion, Entidad, Pago, Proveedor

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
RUTA_BD = RAIZ_PROYECTO / "data" / "trazaunt.sqlite3"
MODELOS = (Entidad, Proveedor, Contratacion, Pago, Alerta, Bitacora)


def crear_motor(ruta: str | Path | None = None) -> Engine:
    """La ruta predeterminada no depende de la carpeta desde donde se ejecuta."""
    if ruta is None and os.getenv("DATABASE_URL"):
        url = make_url(os.environ["DATABASE_URL"])
        if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
            raise ValueError("La demo admite DATABASE_URL de SQLite en archivo.")
        ruta = url.database
    ruta = Path(ruta or RUTA_BD).expanduser().resolve()
    if ruta.is_file() and ruta.stat().st_size:
        # Examina el destino en modo de lectura antes de crear tablas o habilitar WAL.
        with closing(sqlite3.connect(ruta.as_uri()+"?mode=ro", uri=True)) as origen:
            tablas = {r[0] for r in origen.execute("SELECT name FROM sqlite_master WHERE type='table'") if not r[0].startswith("sqlite_")}
            if tablas and (not tablas.issubset(Base.metadata.tables) or not {"proveedores","contrataciones","alertas","bitacora"}.issubset(tablas)):
                raise ValueError("El destino contiene una base ajena al esquema de demostración. Seleccione un archivo nuevo.")
            if tablas and origen.execute("SELECT 1 FROM proveedores WHERE ruc NOT LIKE '00%' LIMIT 1").fetchone():
                raise ValueError("La base contiene proveedores ajenos a la demostración. Use una base sintética separada.")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    motor = create_engine(
        URL.create("sqlite", database=str(ruta)),
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(motor, "connect")
    def activar_integridad(conexion, _registro):
        # SQLite no activa las claves foráneas por defecto.
        cursor = conexion.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return motor


def crear_tablas(motor: Engine) -> None:
    """Crea tablas ausentes; no borra datos ni migra esquemas existentes."""
    Base.metadata.create_all(motor)
    # create_all no agrega índices nuevos a tablas ya existentes.
    for indice in Base.metadata.tables["contrataciones"].indexes:
        indice.create(motor, checkfirst=True)


@contextmanager
def obtener_sesion(motor: Engine):
    """Una transacción por operación, con rollback y cierre si ocurre un error."""
    with Session(motor) as sesion:
        with sesion.begin():
            yield sesion


def contar_registros(sesion: Session) -> dict[str, int]:
    return {
        modelo.__tablename__: sesion.scalar(select(func.count()).select_from(modelo))
        for modelo in MODELOS
    }


def consultar_contrataciones(sesion: Session) -> list[dict]:
    """Datos operativos para reglas, IA e interfaz, sin etiquetas de evaluación."""
    consulta = select(
        Contratacion.id, Contratacion.codigo, Contratacion.entidad_id,
        Contratacion.proveedor_id, Contratacion.objeto, Contratacion.monto,
        Contratacion.fecha, Contratacion.tipo_proceso, Contratacion.n_postores,
        Entidad.nombre.label("entidad"), Proveedor.ruc,
        Proveedor.razon_social.label("proveedor"), Proveedor.fecha_constitucion,
    ).join(Entidad).join(Proveedor).order_by(Contratacion.id)
    return [dict(fila) for fila in sesion.execute(consulta).mappings()]


def consultar_ground_truth(sesion: Session) -> list[dict]:
    """Reservado para evaluación; nunca usar como variable del detector."""
    consulta = select(
        Contratacion.id, Contratacion.es_anomalia_real, Contratacion.tipos_anomalia_real,
    ).order_by(Contratacion.id)
    return [dict(fila) for fila in sesion.execute(consulta).mappings()]


def consultar_pagos(sesion: Session) -> list[dict]:
    """Pagos completos para las reglas; no se filtran por estado de sustento."""
    consulta = select(
        Pago.id, Pago.contratacion_id, Pago.monto, Pago.fecha_pago,
        Pago.tiene_conformidad, Pago.tiene_comprobante,
    ).order_by(Pago.id)
    return [dict(fila) for fila in sesion.execute(consulta).mappings()]
