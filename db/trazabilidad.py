"""Esquema adicional, sin alterar las tablas de TrazaUNT 3.1."""
from sqlalchemy import Column, Integer, String, Text, JSON, ForeignKey, LargeBinary, UniqueConstraint, Boolean
from db.models import Base

class Expediente(Base):
    __tablename__='tz_expedientes'
    id=Column(Integer,primary_key=True,autoincrement=True)
    codigo=Column(String(40),unique=True,nullable=False)
    nombre=Column(String(200),nullable=False)
    objeto=Column(Text,nullable=False)
    tipo=Column(String(30),nullable=False)
    area=Column(String(150),nullable=False)
    responsable=Column(String(150),nullable=False)
    inicio=Column(String(30),nullable=False)
    monto=Column(String(30),nullable=False)
    propietario=Column(String(80),nullable=False)
    convocatoria_id=Column(ForeignKey('convocatorias.id'),unique=True)
    contratacion_id=Column(ForeignKey('contrataciones.id'),unique=True)
    concesion_id=Column(ForeignKey('concesiones.id'),unique=True)
    proveedor_id=Column(ForeignKey('proveedores.id'))
    plantilla=Column(JSON,nullable=False)
    datos=Column(JSON,nullable=False,default=dict)

class Fase(Base):
    __tablename__='tz_fases'
    id=Column(Integer,primary_key=True)
    expediente_id=Column(ForeignKey('tz_expedientes.id'),index=True,nullable=False)
    codigo=Column(String(60),unique=True,nullable=False)
    orden=Column(Integer,nullable=False)
    nombre=Column(String(100),nullable=False)
    estado=Column(String(30),nullable=False,default='pendiente')
    responsable=Column(String(150),nullable=False)
    limite=Column(String(30),nullable=False)
    revision=Column(Integer,nullable=False,default=0)
    __table_args__=(UniqueConstraint('expediente_id','orden'),)

class Requisito(Base):
    __tablename__='tz_requisitos'
    id=Column(Integer,primary_key=True)
    fase_id=Column(ForeignKey('tz_fases.id'),index=True,nullable=False)
    nombre=Column(String(200),nullable=False)
    obligatorio=Column(Boolean,nullable=False,default=True)
    estado=Column(String(30),nullable=False,default='pendiente')

class DocumentoTZ(Base):
    __tablename__='tz_documentos'
    id=Column(Integer,primary_key=True)
    fase_id=Column(ForeignKey('tz_fases.id'),index=True,nullable=False)
    requisito_id=Column(ForeignKey('tz_requisitos.id'),nullable=False)
    nombre=Column(String(150),nullable=False)
    version=Column(Integer,nullable=False)
    sha256=Column(String(64),nullable=False)
    contenido=Column(LargeBinary,nullable=False)
    mime=Column(String(120),nullable=False)
    autor=Column(String(150),nullable=False)
    registrado_por=Column(String(80),nullable=False)
    fecha=Column(String(40),nullable=False)
    estado=Column(String(30),nullable=False,default='presentado')
    __table_args__=(UniqueConstraint('requisito_id','version'),)

class Observacion(Base):
    __tablename__='tz_observaciones'
    id=Column(Integer,primary_key=True)
    fase_id=Column(ForeignKey('tz_fases.id'),index=True,nullable=False)
    requisito_id=Column(ForeignKey('tz_requisitos.id'))
    documento_id=Column(ForeignKey('tz_documentos.id'))
    descripcion=Column(Text,nullable=False)
    autor=Column(String(80),nullable=False)
    responsable=Column(String(150),nullable=False)
    limite=Column(String(30),nullable=False)
    severidad=Column(String(20),nullable=False)
    estado=Column(String(30),nullable=False,default='pendiente')
    respuestas=Column(JSON,nullable=False,default=list)

class Evento(Base):
    __tablename__='tz_eventos'
    id=Column(Integer,primary_key=True)
    expediente_id=Column(ForeignKey('tz_expedientes.id'),index=True,nullable=False)
    fase_id=Column(ForeignKey('tz_fases.id'),index=True)
    actor=Column(String(80),nullable=False)
    responsable=Column(String(150),nullable=False)
    accion=Column(String(50),nullable=False)
    fecha=Column(String(40),nullable=False)
    efectiva=Column(String(40),nullable=False)
    datos=Column(JSON,nullable=False)
    hash=Column(String(64),nullable=False)

class AlertaTZ(Base):
    __tablename__='tz_alertas'
    id=Column(Integer,primary_key=True)
    expediente_id=Column(ForeignKey('tz_expedientes.id'),index=True,nullable=False)
    fase_id=Column(ForeignKey('tz_fases.id'),nullable=False)
    evento_id=Column(ForeignKey('tz_eventos.id'))
    clave=Column(String(180),unique=True,nullable=False)
    regla=Column(String(10),nullable=False)
    descripcion=Column(Text,nullable=False)
    evidencia=Column(JSON,nullable=False)
    fecha=Column(String(40),nullable=False)
    estado=Column(String(30),nullable=False,default='pendiente')
    vigente=Column(Boolean,nullable=False,default=True)
