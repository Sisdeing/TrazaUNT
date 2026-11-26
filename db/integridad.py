"""Tablas aditivas para perfiles, evidencia, vínculos y cobros de concesiones."""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from db.models import Base


class Perfil(Base):
    __tablename__ = "perfiles_proveedor"
    proveedor_id = Column(ForeignKey("proveedores.id"), primary_key=True)
    tipo = Column(String(12), nullable=False)


class EvidenciaIFP(Base):
    __tablename__ = "evidencias_ifp"
    __table_args__ = (UniqueConstraint("proveedor_id", "referencia"),)
    id = Column(Integer, primary_key=True)
    proveedor_id = Column(ForeignKey("proveedores.id"), nullable=False, index=True)
    dimension = Column(String(24), nullable=False)
    valores = Column(JSON, nullable=False)
    origen = Column(String(32), nullable=False)
    referencia = Column(String(150), nullable=False)
    fecha = Column(Date, nullable=False)
    vigente_hasta = Column(Date, nullable=False)
    responsable = Column(String(90), nullable=False)


class EvaluacionIFP(Base):
    __tablename__ = "evaluaciones_ifp"
    id = Column(Integer, primary_key=True)
    proveedor_id = Column(ForeignKey("proveedores.id"), nullable=False, index=True)
    resultado = Column(JSON, nullable=False)
    responsable = Column(String(90), nullable=False)
    fecha = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class Interviniente(Base):
    __tablename__ = "intervinientes_integridad"
    __table_args__ = (UniqueConstraint("proceso", "codigo", "rol"),)
    id = Column(Integer, primary_key=True)
    proceso = Column(String(64), index=True, nullable=False)
    codigo = Column(String(50), nullable=False)
    nombre = Column(String(120), nullable=False)
    rol = Column(String(60), nullable=False)
    registro_completo = Column(Boolean, nullable=False, default=False)


class Vinculo(Base):
    __tablename__ = "vinculos_integridad"
    id = Column(Integer, primary_key=True)
    interviniente_id = Column(
        ForeignKey("intervinientes_integridad.id"), index=True, nullable=False
    )
    proveedor_id = Column(ForeignKey("proveedores.id"), nullable=False, index=True)
    persona = Column(String(90), nullable=False)
    parentesco = Column(String(48), nullable=False)
    grado = Column(Integer)
    cargo = Column(String(40), nullable=False)
    verificado = Column(Boolean, nullable=False)
    evidencia = Column(String(150), nullable=False)
    desde = Column(Date, nullable=False)
    hasta = Column(Date)


class Declaracion(Base):
    __tablename__ = "declaraciones_integridad"
    id = Column(Integer, primary_key=True)
    vinculo_id = Column(
        ForeignKey("vinculos_integridad.id"), index=True, nullable=False
    )
    accion = Column(String(45), nullable=False)
    motivo = Column(String(1000), nullable=False)
    responsable = Column(String(90), nullable=False)
    fecha = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class Concesion(Base):
    __tablename__ = "concesiones"
    id = Column(Integer, primary_key=True)
    convocatoria_id = Column(ForeignKey("convocatorias.id"), unique=True)
    codigo = Column(String(80), nullable=False, unique=True)
    espacio = Column(String(280), nullable=False)
    area = Column(String(160), nullable=False)
    proveedor_id = Column(ForeignKey("proveedores.id"), nullable=False, index=True)
    inicio = Column(Date, nullable=False)
    fin = Column(Date, nullable=False)
    contraprestacion = Column(Numeric(14, 2), nullable=False)
    garantia_hasta = Column(Date)
    ingresos = Column(Numeric(14, 2))
    costos = Column(Numeric(14, 2))


class Cuota(Base):
    __tablename__ = "cuotas_concesion"
    __table_args__ = (UniqueConstraint("concesion_id", "fecha"),)
    id = Column(Integer, primary_key=True)
    concesion_id = Column(ForeignKey("concesiones.id"), index=True, nullable=False)
    fecha = Column(Date, nullable=False)
    exigible = Column(Numeric(14, 2), nullable=False)


class Abono(Base):
    __tablename__ = "abonos_concesion"
    __table_args__ = (
        CheckConstraint("monto > 0"),
        UniqueConstraint("cuota_id", "referencia"),
    )
    id = Column(Integer, primary_key=True)
    cuota_id = Column(ForeignKey("cuotas_concesion.id"), index=True, nullable=False)
    fecha = Column(Date, nullable=False)
    monto = Column(Numeric(14, 2), nullable=False)
    referencia = Column(String(80), nullable=False)
    responsable = Column(String(90), nullable=False)


class Obligacion(Base):
    __tablename__ = "obligaciones_concesion"
    id = Column(Integer, primary_key=True)
    concesion_id = Column(ForeignKey("concesiones.id"), index=True, nullable=False)
    nombre = Column(String(140), nullable=False)
    vence = Column(Date, nullable=False)
    cumplida = Column(Date)
