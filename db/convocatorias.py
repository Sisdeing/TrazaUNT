"""Entidades del flujo de convocatoria. Los documentos se almacenan fuera del contenido público."""

from datetime import datetime, timezone
from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import deferred
from db.models import Base


def ahora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Convocatoria(Base):
    __tablename__ = "convocatorias"
    id = Column(Integer, primary_key=True)
    codigo = Column(String(40), nullable=False, unique=True)
    nombre = Column(String(200), nullable=False)
    modalidad = Column(String(90), nullable=False)
    area = Column(String(160), nullable=False)
    objeto = Column(Text, nullable=False)
    presupuesto = Column(Numeric(14, 2), nullable=False)
    duracion_meses = Column(Integer, nullable=False)
    apertura = Column(Date, nullable=False)
    cierre = Column(Date, nullable=False)
    responsable = Column(String(120), nullable=False)
    descripcion = Column(Text, nullable=False, default="")
    ubicacion = Column(String(200), nullable=False, default="")
    requisitos = Column(JSON, nullable=False)
    criterios = Column(JSON, nullable=False)
    intervinientes = Column(JSON, nullable=False)
    estado = Column(String(32), nullable=False, default="borrador", index=True)
    version = Column(Integer, nullable=False, default=1)
    version_bases = Column(Integer, nullable=False, default=1)
    resultado = Column(JSON)


class Postulacion(Base):
    __tablename__ = "postulaciones"
    __table_args__ = (
        UniqueConstraint("convocatoria_id", "proveedor_id"),
        CheckConstraint("oferta > 0"),
    )
    id = Column(Integer, primary_key=True)
    convocatoria_id = Column(ForeignKey("convocatorias.id"), nullable=False, index=True)
    proveedor_id = Column(ForeignKey("proveedores.id"), nullable=False)
    oferta = Column(Numeric(14, 2), nullable=False)
    experiencia = Column(Integer, nullable=False)
    fecha = Column(DateTime, nullable=False, default=ahora)
    version_bases = Column(Integer, nullable=False)


class Documento(Base):
    __tablename__ = "documentos"
    id = Column(Integer, primary_key=True)
    convocatoria_id = Column(ForeignKey("convocatorias.id"), nullable=False, index=True)
    postulante_id = Column(ForeignKey("postulaciones.id"), index=True)
    nombre = Column(String(160), nullable=False)
    tipo = Column(String(30), nullable=False)
    mime = Column(String(120), nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    tamano = Column(Integer, nullable=False)
    version = Column(Integer, nullable=False)
    version_bases = Column(Integer, nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    estado = Column(String(40), nullable=False, default="recibido")
    campos = Column(JSON, nullable=False, default=list)
    observaciones = Column(JSON, nullable=False, default=list)
    fecha = Column(DateTime, nullable=False, default=ahora)
    contenido = deferred(Column(LargeBinary, nullable=False))


class EventoConvocatoria(Base):
    __tablename__ = "eventos_convocatoria"
    id = Column(Integer, primary_key=True)
    convocatoria_id = Column(ForeignKey("convocatorias.id"), nullable=False, index=True)
    documento_id = Column(ForeignKey("documentos.id"))
    postulante_id = Column(ForeignKey("postulaciones.id"))
    autor = Column(String(120), nullable=False)
    accion = Column(String(60), nullable=False)
    motivo = Column(Text, nullable=False)
    fecha = Column(DateTime, nullable=False, default=ahora)
    datos = Column(JSON, nullable=False, default=dict)


class NotaCriterio(Base):
    __tablename__ = "evaluaciones_propuestas"
    id = Column(Integer, primary_key=True)
    postulante_id = Column(ForeignKey("postulaciones.id"), nullable=False, index=True)
    documento_id = Column(ForeignKey("documentos.id"), nullable=False)
    criterio = Column(String(160), nullable=False)
    puntaje = Column(Numeric(5, 2), nullable=False)
    version_bases = Column(Integer, nullable=False)
    ubicacion = Column(String(160), nullable=False)
    autor = Column(String(100), nullable=False)
    motivo = Column(Text, nullable=False)
    fecha = Column(DateTime, nullable=False, default=ahora)
