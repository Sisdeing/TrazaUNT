"""Tablas aditivas: coincidencias entre personas y empresas, admisión de postulantes y cuentas de empresa.

Ninguna tabla anterior se modifica. Las coincidencias son señales para revisión humana,
no determinaciones de conflicto de intereses.
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from db.models import Base


def ahora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Coincidencia(Base):
    __tablename__ = "coincidencias"
    id = Column(Integer, primary_key=True)
    ambito = Column(String(20), nullable=False, index=True)  # convocatoria
    referencia_id = Column(Integer, nullable=False, index=True)
    clave = Column(String(240), nullable=False, unique=True)
    tipo = Column(String(8), nullable=False)
    nivel = Column(String(10), nullable=False)  # alta, media, baja
    titulo = Column(String(160), nullable=False)
    detalle = Column(Text, nullable=False)
    sujeto_a = Column(JSON, nullable=False)
    sujeto_b = Column(JSON, nullable=False)
    evidencia = Column(JSON, nullable=False)
    estado = Column(String(20), nullable=False, default="pendiente")
    vigente = Column(Boolean, nullable=False, default=True)
    detectada = Column(DateTime, nullable=False, default=ahora)
    actualizada = Column(DateTime, nullable=False, default=ahora)


class RevisionCoincidencia(Base):
    __tablename__ = "revisiones_coincidencia"
    id = Column(Integer, primary_key=True)
    coincidencia_id = Column(ForeignKey("coincidencias.id"), nullable=False, index=True)
    decision = Column(String(20), nullable=False)
    justificacion = Column(Text, nullable=False)
    autor = Column(String(150), nullable=False)
    cuenta = Column(String(80), nullable=False)
    fecha = Column(DateTime, nullable=False, default=ahora)


class Admision(Base):
    """Historial de decisiones de admisión. El estado vigente es el último registro."""

    __tablename__ = "admisiones_postulacion"
    id = Column(Integer, primary_key=True)
    postulacion_id = Column(ForeignKey("postulaciones.id"), nullable=False, index=True)
    estado = Column(String(20), nullable=False)
    motivo = Column(Text, nullable=False)
    autor = Column(String(150), nullable=False)
    fecha = Column(DateTime, nullable=False, default=ahora)


class CuentaEmpresa(Base):
    """Vincula una cuenta local de perfil empresa con su registro de proveedor."""

    __tablename__ = "cuentas_empresa"
    usuario = Column(String(80), primary_key=True)
    proveedor_id = Column(ForeignKey("proveedores.id"), nullable=False, index=True)


class SeguimientoAlerta(Base):
    """Marca «en revisión» común a las alertas de reglas, coincidencias y trazabilidad.

    Tabla aditiva (v5.1): no modifica los estados propios de cada origen. Una alerta se
    muestra «en revisión» si tiene esta marca y su estado de origen sigue pendiente.
    """
    __tablename__ = "seguimiento_alertas"
    uid = Column(String(40), primary_key=True)
    responsable = Column(String(150), nullable=False)
    cuenta = Column(String(80), nullable=False)
    fecha = Column(DateTime, nullable=False, default=ahora)
