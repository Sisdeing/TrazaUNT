"""Tablas del proyecto. Una alerta es una señal para revisión, no una acusación."""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, Column, Date, DateTime, Index,
    ForeignKey, Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, deferred, relationship

Base = declarative_base()


class Entidad(Base):
    __tablename__ = "entidades"

    id = Column(Integer, primary_key=True)
    codigo = Column(String(30), nullable=False, unique=True)
    nombre = Column(String(200), nullable=False)


class Proveedor(Base):
    __tablename__ = "proveedores"
    __table_args__ = (CheckConstraint("length(ruc) = 11", name="ruc_11_caracteres"),)

    id = Column(Integer, primary_key=True)
    # Los RUC de la simulación empiezan con 00: no son registros para uso real.
    ruc = Column(String(11), nullable=False, unique=True)
    razon_social = Column(String(250), nullable=False)
    fecha_constitucion = Column(Date, nullable=False)
    domicilio = Column(String(300), nullable=False)
    representante = Column(String(200), nullable=False)


class Contratacion(Base):
    __tablename__ = "contrataciones"
    __table_args__ = (
        CheckConstraint("monto > 0", name="contratacion_monto_positivo"),
        Index("ix_contratacion_entidad_proveedor_fecha", "entidad_id", "proveedor_id", "fecha"),
        CheckConstraint("n_postores >= 1", name="contratacion_postores_validos"),
    )

    id = Column(Integer, primary_key=True)
    codigo = Column(String(30), nullable=False, unique=True)
    entidad_id = Column(Integer, ForeignKey("entidades.id"), nullable=False, index=True)
    proveedor_id = Column(Integer, ForeignKey("proveedores.id"), nullable=False, index=True)
    objeto = Column(String(300), nullable=False)
    monto = Column(Numeric(14, 2), nullable=False)
    fecha = Column(Date, nullable=False, index=True)
    tipo_proceso = Column(String(100), nullable=False)
    n_postores = Column(Integer, nullable=False)

    # Etiquetas de evaluación. deferred evita cargarlas en consultas ORM comunes.
    # No es control de acceso: quien abre SQLite puede leerlas.
    es_anomalia_real = deferred(Column(Boolean, nullable=False, default=False))
    tipos_anomalia_real = deferred(Column(JSON, nullable=False, default=list))

    entidad = relationship("Entidad")
    proveedor = relationship("Proveedor")
    pagos = relationship("Pago", back_populates="contratacion")
    alertas = relationship("Alerta", back_populates="contratacion")


class Pago(Base):
    __tablename__ = "pagos"
    __table_args__ = (CheckConstraint("monto > 0", name="pago_monto_positivo"),)

    id = Column(Integer, primary_key=True)
    contratacion_id = Column(Integer, ForeignKey("contrataciones.id"), nullable=False, index=True)
    monto = Column(Numeric(14, 2), nullable=False)
    # Permitimos fechas incoherentes para que luego las detecte el motor de reglas.
    fecha_pago = Column(Date, nullable=False)
    tiene_conformidad = Column(Boolean, nullable=False)
    tiene_comprobante = Column(Boolean, nullable=False)

    contratacion = relationship("Contratacion", back_populates="pagos")


class Alerta(Base):
    __tablename__ = "alertas"
    __table_args__ = (
        UniqueConstraint("contratacion_id", "regla_id", name="alerta_por_regla"),
        CheckConstraint("score >= 0 AND score <= 100", name="alerta_score_valido"),
        CheckConstraint("severidad IN ('baja', 'media', 'alta')", name="alerta_severidad_valida"),
        CheckConstraint("estado IN ('pendiente', 'confirmada', 'descartada')", name="alerta_estado_valido"),
    )

    id = Column(Integer, primary_key=True)
    contratacion_id = Column(Integer, ForeignKey("contrataciones.id"), nullable=False, index=True)
    regla_id = Column(String(60), nullable=False)
    severidad = Column(String(10), nullable=False)
    score = Column(Numeric(5, 2), nullable=False, default=0)
    evidencia_json = Column(JSON, nullable=False, default=dict)
    explicacion = Column(Text, nullable=False)
    estado = Column(String(20), nullable=False, default="pendiente", index=True)

    contratacion = relationship("Contratacion", back_populates="alertas")
    movimientos = relationship("Bitacora", back_populates="alerta")


class Bitacora(Base):
    __tablename__ = "bitacora"

    id = Column(Integer, primary_key=True)
    alerta_id = Column(Integer, ForeignKey("alertas.id"), nullable=False, index=True)
    accion = Column(String(40), nullable=False)
    analista = Column(String(150), nullable=False)
    comentario = Column(Text, nullable=False)
    # SQLite almacena UTC sin zona; convertir a America/Lima al mostrar en Fase 4.
    fecha = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    alerta = relationship("Alerta", back_populates="movimientos")
