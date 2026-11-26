"""Perfil Empresa: cada empresa consulta solo sus propias postulaciones.

Ve la información general de la convocatoria, el avance del proceso, el estado de
admisión decidido por la universidad y el estado de revisión de sus documentos. No ve
a los demás postulantes, las señales internas del análisis documental, las
coincidencias ni los nombres de los intervinientes de la universidad.
"""
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import false, or_, select

from db.convocatorias import Convocatoria, Documento, EventoConvocatoria, Postulacion
from db.database import obtener_sesion
from db.models import Proveedor
from services.coincidencias import detectar_convocatoria
from services.convocatorias import (
    ADMISION, admisiones, buscar, fecha_lima, guardar_archivo, leer_formulario, registrar, transaccion,
)


def empresa(request: Request):
    user = getattr(request.state, "usuario", None)
    if not user or user.get("rol") != "empresa" or not user.get("proveedor_id"):
        raise HTTPException(403, "Esta sección corresponde al perfil empresa.")
    return user


router = APIRouter(prefix="/api/empresa", tags=["Perfil empresa"], dependencies=[Depends(empresa)])

ETAPAS = [
    ("abierta", "Recepción de propuestas"),
    ("cerrada", "Recepción cerrada"),
    ("en_evaluacion", "Evaluación por el comité"),
    ("resultado_registrado", "Resultado registrado"),
]
ESTADOS = {"borrador": "En preparación", "abierta": "Recepción abierta", "cerrada": "Recepción cerrada",
           "en_evaluacion": "En evaluación", "resultado_registrado": "Resultado registrado", "cancelada": "Cancelada"}
PUBLICOS = {"apertura_simulada": "Inicio de la recepción de propuestas", "abierta": "Inicio de la recepción de propuestas",
            "cerrada": "Cierre de la recepción", "en_evaluacion": "Inicio de la evaluación",
            "resultado_registrado": "Registro del resultado", "cancelada": "Convocatoria cancelada"}
PROPIOS = {"inscripcion": "Postulación registrada", "postulacion_empresa": "Postulación enviada por la empresa",
           "carga_documental": "Documento recibido", "analisis": "Lectura automática del documento",
           "validacion_documental": "Documento revisado por la universidad",
           "revision": "Revisión registrada por la universidad", "admision": "Decisión de admisión"}


class Postular(BaseModel):
    model_config = ConfigDict(extra="forbid")
    oferta: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
    experiencia: int = Field(ge=0, le=150)


def proveedor_de(s, user):
    v = s.get(Proveedor, user["proveedor_id"])
    if v is None:
        raise HTTPException(404, "La empresa vinculada a esta cuenta no existe.")
    return v


def postulacion_de(s, cid, user):
    return s.scalar(select(Postulacion).where(Postulacion.convocatoria_id == cid,
                                              Postulacion.proveedor_id == user["proveedor_id"]))


def estado_documento(d, revisado):
    if revisado:
        return "revisado", "Revisado por la universidad"
    if d.estado == "error_lectura":
        return "atencion", "No se pudo leer el archivo; la universidad podría solicitar una nueva versión"
    if d.estado in ("analizado", "requiere_revision"):
        return "en_revision", "En revisión por la universidad"
    return "recibido", "Recibido"


def documentos_de(s, c, p):
    if p is None:
        return []
    revisados = {e.documento_id for e in s.scalars(select(EventoConvocatoria).where(
        EventoConvocatoria.convocatoria_id == c.id, EventoConvocatoria.postulante_id == p.id,
        EventoConvocatoria.accion == "validacion_documental"))}
    salida = []
    for d in s.scalars(select(Documento).where(Documento.convocatoria_id == c.id, Documento.postulante_id == p.id)
                       .order_by(Documento.id.desc())):
        clave, texto = estado_documento(d, d.id in revisados)
        salida.append(dict(id=d.id, nombre=d.nombre, tipo=d.tipo, version=d.version, sha256=d.sha256,
                           tamano=d.tamano, fecha=fecha_lima(d.fecha), estado=clave, estado_texto=texto))
    return salida


def etapas(c):
    if c.estado == "cancelada":
        return [dict(clave="cancelada", nombre="Convocatoria cancelada", estado="actual")]
    orden = [k for k, _ in ETAPAS]
    actual = orden.index(c.estado) if c.estado in orden else -1
    return [dict(clave=k, nombre=n, estado="completa" if i < actual else "actual" if i == actual else "pendiente")
            for i, (k, n) in enumerate(ETAPAS)]


def resumen_convocatoria(s, c, p):
    adm = admisiones(s, p.id) if p else []
    ultimo = adm[-1]["estado"] if adm else "pendiente"
    resultado = None
    if c.resultado and p:
        resultado = "seleccionada" if c.resultado.get("postulante_id") == p.id else "no_seleccionada"
    return dict(id=c.id, codigo=c.codigo, nombre=c.nombre.removesuffix(" — DEMO"), modalidad=c.modalidad, area=c.area,
                estado=c.estado, estado_texto=ESTADOS.get(c.estado, c.estado), apertura=c.apertura.isoformat(),
                cierre=c.cierre.isoformat(), postulado=p is not None,
                admision=ultimo if p else None, admision_texto=ADMISION[ultimo] if p else None,
                documentos=len(documentos_de(s, c, p)) if p else 0, resultado=resultado,
                puede_postular=p is None and c.estado == "abierta")


@router.get("/resumen")
def resumen(request: Request):
    user = empresa(request)
    with obtener_sesion(request.app.state.motor) as s:
        v = proveedor_de(s, user)
        propias = {p.convocatoria_id: p for p in s.scalars(select(Postulacion).where(Postulacion.proveedor_id == v.id))}
        visibles = s.scalars(select(Convocatoria).where(or_(
            Convocatoria.id.in_(list(propias)) if propias else false(), Convocatoria.estado == "abierta")).order_by(Convocatoria.id.desc()))
        items = [resumen_convocatoria(s, c, propias.get(c.id)) for c in visibles]
        return dict(empresa=dict(razon_social=v.razon_social, ruc=v.ruc),
                    postulaciones=[x for x in items if x["postulado"]],
                    disponibles=[x for x in items if not x["postulado"]])


@router.get("/convocatorias/{cid}")
def ficha(cid: int, request: Request):
    user = empresa(request)
    with obtener_sesion(request.app.state.motor) as s:
        c = buscar(s, Convocatoria, cid)
        p = postulacion_de(s, cid, user)
        if p is None and c.estado != "abierta":
            raise HTTPException(404, "Convocatoria no disponible para esta empresa.")
        eventos = []
        for e in s.scalars(select(EventoConvocatoria).where(EventoConvocatoria.convocatoria_id == cid).order_by(EventoConvocatoria.id)):
            if e.accion in PUBLICOS and e.postulante_id in (None, p.id if p else None):
                eventos.append(dict(fecha=fecha_lima(e.fecha), titulo=PUBLICOS[e.accion], tipo="proceso"))
            elif p and e.postulante_id == p.id and e.accion in PROPIOS:
                detalle = e.motivo if e.accion == "admision" else None
                eventos.append(dict(fecha=fecha_lima(e.fecha), titulo=PROPIOS[e.accion], tipo="empresa", detalle=detalle))
        return dict(
            **resumen_convocatoria(s, c, p),
            objeto=c.objeto, descripcion=c.descripcion, ubicacion=c.ubicacion, presupuesto=float(c.presupuesto),
            duracion_meses=c.duracion_meses, requisitos=c.requisitos, criterios=c.criterios,
            comite=f"{len([i for i in c.intervinientes if 'comit' in (i.get('rol') or '').lower()])} miembro(s) registrados",
            etapas=etapas(c),
            postulacion=dict(oferta=float(p.oferta), experiencia=p.experiencia, fecha=fecha_lima(p.fecha)) if p else None,
            admisiones=[{k: a[k] for k in ("estado", "estado_texto", "motivo", "fecha")} for a in admisiones(s, p.id)] if p else [],
            documentos_propios=documentos_de(s, c, p),
            historial=list(reversed(eventos)),
            aviso="Solo se muestra información de tu propia postulación. Las decisiones corresponden al comité de la universidad.",
        )


@router.post("/convocatorias/{cid}/postulacion", status_code=201)
def postular(cid: int, datos: Postular, request: Request):
    user = empresa(request)
    with transaccion(request.app.state.motor) as s:
        c = buscar(s, Convocatoria, cid)
        if c.estado != "abierta":
            raise HTTPException(409, "La recepción de propuestas no está abierta.")
        if postulacion_de(s, cid, user):
            raise HTTPException(409, "Tu empresa ya postuló a esta convocatoria.")
        p = Postulacion(convocatoria_id=cid, proveedor_id=user["proveedor_id"], oferta=datos.oferta,
                        experiencia=datos.experiencia, version_bases=c.version_bases)
        s.add(p)
        s.flush()
        registrar(s, c, user["nombre"], "postulacion_empresa", "Postulación enviada desde el perfil empresa.", p.id)
        # Registrar una empresa activa la comparación automática de personas y empresas.
        detectar_convocatoria(s, c)
    return ficha(cid, request)


@router.post("/convocatorias/{cid}/documentos", status_code=201)
async def subir(cid: int, request: Request):
    user = empresa(request)
    nombre, mime, contenido, tipo, _ = await leer_formulario(request)
    if tipo == "bases":
        raise HTTPException(422, "Las bases las publica la universidad.")
    with transaccion(request.app.state.motor) as s:
        c = buscar(s, Convocatoria, cid)
        p = postulacion_de(s, cid, user)
        if p is None:
            raise HTTPException(409, "Primero registra la postulación de tu empresa.")
        if c.estado != "abierta":
            raise HTTPException(409, "La recepción de documentos está cerrada.")
        guardar_archivo(s, c, p.id, tipo, nombre, mime, contenido, user["nombre"])
    return ficha(cid, request)
