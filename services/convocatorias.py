"""Gestión local de convocatorias y lectura documental con decisiones humanas trazables."""

from calendar import monthrange
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import select, func, or_
from starlette.datastructures import UploadFile

from db.convocatorias import Convocatoria, Documento, EventoConvocatoria, Postulacion
from db.database import obtener_sesion
from db.models import Proveedor
from services.trazadocs import MAX_BYTES, analizar_aislado, normal, validar_archivo
from services.evaluacion_documental import comparar, calificaciones
from services.coincidencias import detectar_convocatoria, resumen_convocatoria
from db.coincidencias import Admision


def privado(request: Request):
    user = getattr(request.state, "usuario", None)
    if not user:
        raise HTTPException(401, "Inicia sesión para acceder.")
    if user.get("rol") not in ("analista", "administrador"):
        raise HTTPException(
            403, "El expediente de evaluación requiere acceso de analista."
        )
    return user


router = APIRouter(
    prefix="/api", tags=["Convocatorias y TrazaDocs"], dependencies=[Depends(privado)]
)
Texto = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)
]
Importe = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
Tipo = Literal["bases", "propuesta", "anexo", "garantia", "otro"]
LIMA = timezone(timedelta(hours=-5))
CARPETA_DEMO = Path(__file__).resolve().parents[1] / "data/demo/cafeteria"


class Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Criterio(Entrada):
    nombre: Texto
    peso: Annotated[Decimal, Field(gt=0, le=100, decimal_places=2)]


class Interviniente(Entrada):
    nombre: Texto
    rol: Texto
    documento: str | None = Field(default=None, pattern=r"^\d{8}$")


class Bases(Entrada):
    codigo: str = Field(pattern=r"^[\w.-]{2,40}$")
    nombre: Texto
    modalidad: Texto
    area: Texto
    objeto: str = Field(min_length=3, max_length=3000)
    presupuesto: Importe
    duracion_meses: int = Field(ge=1, le=600)
    apertura: date
    cierre: date
    responsable: Texto
    descripcion: str = Field(default="", max_length=3000)
    ubicacion: str = Field(default="", max_length=160)
    requisitos: list[Texto] = Field(min_length=1, max_length=50)
    criterios: list[Criterio] = Field(min_length=1, max_length=30)
    intervinientes: list[Interviniente] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validar(self):
        if self.cierre < self.apertura or self.cierre.year > 9900:
            raise ValueError("Revise el intervalo de recepción.")
        if sum(c.peso for c in self.criterios) != 100:
            raise ValueError("Los pesos deben sumar 100.")
        for campos in (self.requisitos, [c.nombre for c in self.criterios]):
            if len({normal(n) for n in campos}) != len(campos):
                raise ValueError(
                    "Los requisitos y criterios deben ser únicos en su grupo."
                )
        return self


class Modificacion(Bases):
    version: int = Field(ge=1)


class AltaPostulante(Entrada):
    proveedor_id: int = Field(gt=0)
    oferta: Importe
    experiencia: int = Field(ge=0, le=150)


class Revision(Entrada):
    motivo: str = Field(min_length=3, max_length=2000)
    postulante_id: int | None = Field(default=None, gt=0)


class Transicion(Revision):
    estado: Literal[
        "abierta", "cerrada", "en_evaluacion", "resultado_registrado", "cancelada"
    ]
    version: int = Field(ge=1)


class DecisionAdmision(Entrada):
    estado: Literal["admitida", "observada", "no_admitida"]
    motivo: str = Field(min_length=8, max_length=2000)


ADMISION = {"pendiente": "Pendiente de revisión", "admitida": "Admitida", "observada": "Observada", "no_admitida": "No admitida"}


class Correccion(Entrada):
    indice: int = Field(ge=0)
    revision: int = Field(ge=1)
    estado: Literal["confirmado", "corregido", "descartado"]
    valor: str | None = Field(default=None, max_length=300)
    motivo: str = Field(min_length=3, max_length=2000)


def fecha_lima(dt):
    return dt.replace(tzinfo=timezone.utc).astimezone(LIMA).isoformat()


@contextmanager
def transaccion(motor):
    with obtener_sesion(motor) as sesion:
        if motor.dialect.name == "sqlite":
            sesion.connection().exec_driver_sql("BEGIN IMMEDIATE")
        yield sesion


def buscar(s, modelo, identificador):
    elemento = s.get(modelo, identificador)
    if elemento is None:
        raise HTTPException(404, "Registro no encontrado.")
    return elemento


def registrar(
    s, c, autor, accion, motivo, postulante_id=None, documento_id=None, datos=None
):
    s.add(
        EventoConvocatoria(
            convocatoria_id=c.id,
            autor=autor,
            accion=accion,
            motivo=motivo,
            postulante_id=postulante_id,
            documento_id=documento_id,
            datos=datos or {},
        )
    )


def base_dict(c):
    return dict(
        id=c.id,
        codigo=c.codigo,
        nombre=c.nombre.removesuffix(" — DEMO") if c.codigo == "CAF-DEMO-001" else c.nombre,
        modalidad=c.modalidad,
        area=c.area,
        objeto=c.objeto,
        presupuesto=float(c.presupuesto),
        duracion_meses=c.duracion_meses,
        apertura=c.apertura.isoformat(),
        cierre=c.cierre.isoformat(),
        responsable=c.responsable,
        descripcion=c.descripcion,
        ubicacion=c.ubicacion,
        requisitos=c.requisitos,
        criterios=c.criterios,
        intervinientes=c.intervinientes,
        estado=c.estado,
        version=c.version,
        version_bases=c.version_bases,
        resultado=c.resultado,
    )


def admisiones(s, pid):
    return [
        dict(estado=a.estado, estado_texto=ADMISION[a.estado], motivo=a.motivo, autor=a.autor, fecha=fecha_lima(a.fecha))
        for a in s.scalars(select(Admision).where(Admision.postulacion_id == pid).order_by(Admision.id))
    ]


def ficha_postulante(p, proveedor, historial=None):
    historial = historial or []
    ultimo = historial[-1] if historial else None
    return dict(
        admision=ultimo["estado"] if ultimo else "pendiente",
        admision_texto=ADMISION[ultimo["estado"] if ultimo else "pendiente"],
        admisiones=historial,
        id=p.id,
        proveedor_id=p.proveedor_id,
        ruc=proveedor.ruc,
        razon_social=proveedor.razon_social,
        representante=proveedor.representante,
        oferta=float(p.oferta),
        experiencia=p.experiencia,
        fecha=fecha_lima(p.fecha),
        version_bases=p.version_bases,
    )


def fichadoc(d, completa=False):
    datos = dict(
        id=d.id,
        convocatoria_id=d.convocatoria_id,
        postulante_id=d.postulante_id,
        nombre=d.nombre,
        tipo=d.tipo,
        mime=d.mime,
        tamano=d.tamano,
        version=d.version,
        estado=d.estado,
        sha256=d.sha256,
        fecha=fecha_lima(d.fecha),
        revision=d.revision,
        version_bases=d.version_bases,
    )
    if completa:
        datos.update(campos=d.campos, observaciones=d.observaciones)
    return datos


def lista_postulantes(s, c):
    filas = s.execute(
        select(Postulacion, Proveedor)
        .join(Proveedor)
        .where(Postulacion.convocatoria_id == c.id)
        .order_by(Postulacion.id)
    )
    return [ficha_postulante(p, v, admisiones(s, p.id)) for p, v in filas]


def detalle(s, c):
    return dict(
        **base_dict(c),
        postulantes=lista_postulantes(s, c),
        coincidencias=resumen_convocatoria(s, c.id),
        documentos=[
            fichadoc(d)
            for d in s.scalars(
                select(Documento)
                .where(Documento.convocatoria_id == c.id)
                .order_by(Documento.id.desc())
            )
        ],
        historial=[
            dict(
                id=e.id,
                accion=e.accion,
                motivo=e.motivo,
                autor=e.autor,
                fecha=fecha_lima(e.fecha),
                documento_id=e.documento_id,
                postulante_id=e.postulante_id,
            )
            for e in s.scalars(
                select(EventoConvocatoria)
                .where(EventoConvocatoria.convocatoria_id == c.id)
                .order_by(EventoConvocatoria.id.desc())
                .limit(100)
            )
        ],
    )


def preparar(datos):
    return {
        **datos.model_dump(exclude={"criterios", "intervinientes", "version"}),
        "criterios": [
            dict(nombre=c.nombre, peso=float(c.peso)) for c in datos.criterios
        ],
        "intervinientes": [p.model_dump() for p in datos.intervinientes],
    }


def unico(s, codigo, actual=0):
    if s.scalar(
        select(Convocatoria.id).where(
            Convocatoria.codigo == codigo, Convocatoria.id != actual
        )
    ):
        raise HTTPException(409, "El código ya existe.")


def comprobar_version(version, c):
    if version != c.version:
        raise HTTPException(
            409, "El registro cambió. Actualice la ficha antes de continuar."
        )


def postulante_local(s, c, pid):
    p = buscar(s, Postulacion, pid)
    if p.convocatoria_id != c.id:
        raise HTTPException(404, "Postulante no localizado en esta convocatoria.")
    return p


def nueva_version(s, c, pid, nombre):
    n = s.scalar(
        select(func.max(Documento.version)).where(
            Documento.convocatoria_id == c.id,
            Documento.postulante_id == pid,
            Documento.nombre == nombre,
        )
    )
    return (n or 0) + 1


def guardar_archivo(s, c, pid, tipo, nombre, mime, contenido, autor):
    try:
        mime, huella = validar_archivo(nombre, mime, contenido)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    duplicado = s.scalar(
        select(Documento.id).where(
            Documento.convocatoria_id == c.id,
            Documento.postulante_id == pid,
            Documento.sha256 == huella,
        )
    )
    if duplicado:
        raise HTTPException(
            409, f"Ya existe un documento idéntico en este expediente (#{duplicado})."
        )
    if (
        s.scalar(
            select(func.count())
            .select_from(Documento)
            .where(Documento.convocatoria_id == c.id)
        )
        >= 300
    ):
        raise HTTPException(
            409, "Se alcanzó el máximo de 300 archivos por convocatoria."
        )
    doc = Documento(
        convocatoria_id=c.id,
        postulante_id=pid,
        tipo=tipo,
        nombre=nombre,
        mime=mime,
        sha256=huella,
        contenido=contenido,
        tamano=len(contenido),
        version=nueva_version(s, c, pid, nombre),
        version_bases=c.version_bases,
    )
    s.add(doc)
    s.flush()
    registrar(s, c, autor, "carga_documental", nombre, pid, doc.id)
    return doc


@router.get("/convocatorias")
def listar(
    request: Request,
    q: str = Query("", max_length=160),
    estado: str = Query("", max_length=40),
    pagina: int = Query(1, ge=1),
    tamano: int = Query(25, ge=1, le=100),
):
    consulta = select(Convocatoria)
    if q.strip():
        consulta = consulta.where(
            or_(
                Convocatoria.nombre.contains(q.strip(), autoescape=True),
                Convocatoria.codigo.contains(q.strip(), autoescape=True),
            )
        )
    if estado and estado not in ("todas", "todos"):
        consulta = consulta.where(Convocatoria.estado == estado)
    with obtener_sesion(request.app.state.motor) as s:
        total = s.scalar(select(func.count()).select_from(consulta.subquery()))
        filas = s.scalars(
            consulta.order_by(Convocatoria.id.desc())
            .offset((pagina - 1) * tamano)
            .limit(tamano)
        )
        return dict(
            items=[base_dict(c) for c in filas],
            total=total,
            pagina=pagina,
            tamano=tamano,
        )


@router.post("/convocatorias", status_code=201)
def crear(request: Request, datos: Bases):
    with transaccion(request.app.state.motor) as s:
        unico(s, datos.codigo)
        c = Convocatoria(**preparar(datos))
        s.add(c)
        s.flush()
        registrar(
            s,
            c,
            privado(request)["nombre"],
            "creacion",
            "Borrador creado.",
            datos=base_dict(c),
        )
        detectar_convocatoria(s, c)
        return detalle(s, c)


@router.get("/convocatorias/{cid}")
def obtener(cid: int, request: Request):
    with obtener_sesion(request.app.state.motor) as s:
        return detalle(s, buscar(s, Convocatoria, cid))


@router.patch("/convocatorias/{cid}")
def editar(cid: int, request: Request, datos: Modificacion):
    with transaccion(request.app.state.motor) as s:
        c = buscar(s, Convocatoria, cid)
        comprobar_version(datos.version, c)
        if c.estado != "borrador":
            raise HTTPException(409, "Las bases quedan congeladas desde la apertura.")
        unico(s, datos.codigo, c.id)
        antes = base_dict(c)
        for clave, valor in preparar(datos).items():
            setattr(c, clave, valor)
        c.version += 1
        c.version_bases += 1
        registrar(
            s,
            c,
            privado(request)["nombre"],
            "edicion",
            "Nueva versión de las bases.",
            datos={"antes": antes, "despues": base_dict(c)},
        )
        detectar_convocatoria(s, c)
        return detalle(s, c)


@router.post("/convocatorias/{cid}/postulantes", status_code=201)
def inscribir(cid: int, request: Request, datos: AltaPostulante):
    with transaccion(request.app.state.motor) as s:
        c = buscar(s, Convocatoria, cid)
        if c.estado != "abierta":
            raise HTTPException(409, "La recepción de propuestas está cerrada.")
        proveedor = buscar(s, Proveedor, datos.proveedor_id)
        if s.scalar(
            select(Postulacion.id).where(
                Postulacion.convocatoria_id == cid,
                Postulacion.proveedor_id == proveedor.id,
            )
        ):
            raise HTTPException(409, "Este proveedor ya está inscrito.")
        postulante = Postulacion(
            convocatoria_id=cid, version_bases=c.version_bases, **datos.model_dump()
        )
        s.add(postulante)
        s.flush()
        registrar(
            s,
            c,
            privado(request)["nombre"],
            "inscripcion",
            "Registro interno del postulante.",
            postulante.id,
        )
        detectar_convocatoria(s, c)
        return detalle(s, c)


async def leer_formulario(request):
    total = 0
    partes = []
    async for bloque in request.stream():
        total += len(bloque)
        if total > MAX_BYTES + 65536:
            raise HTTPException(413, "El archivo supera el límite de 4 MiB.")
        partes.append(bloque)
    cuerpo = b"".join(partes)

    async def recibir():
        return {"type": "http.request", "body": cuerpo, "more_body": False}

    limitada = Request(request.scope, recibir)
    async with limitada.form(max_files=1, max_fields=2, max_part_size=1024) as form:
        archivo = form.get("archivo")
        tipo = form.get("tipo")
        if not isinstance(archivo, UploadFile) or tipo not in (
            "bases",
            "propuesta",
            "anexo",
            "garantia",
            "otro",
        ):
            raise HTTPException(
                422, "Indique un archivo y un tipo documental admitido."
            )
        raw_id = form.get("postulante_id")
        if raw_id not in (None, "") and not (
            isinstance(raw_id, str)
            and raw_id.isascii()
            and raw_id.isdecimal()
            and len(raw_id) < 15
        ):
            raise HTTPException(422, "El postulante indicado no es válido.")
        return (
            archivo.filename,
            archivo.content_type,
            await archivo.read(MAX_BYTES + 1),
            tipo,
            int(raw_id) if raw_id else None,
        )


@router.post("/convocatorias/{cid}/documentos", status_code=201)
async def subir(cid: int, request: Request):
    nombre, mime, contenido, tipo, pid = await leer_formulario(request)
    with transaccion(request.app.state.motor) as s:
        c = buscar(s, Convocatoria, cid)
        if tipo == "bases":
            if pid is not None or c.estado != "borrador":
                raise HTTPException(
                    409, "Adjunte las bases al borrador antes de abrir la recepción."
                )
        else:
            if not pid or c.estado != "abierta":
                raise HTTPException(
                    409, "Se requiere una recepción abierta y un postulante."
                )
            postulante_local(s, c, pid)
        doc = guardar_archivo(
            s, c, pid, tipo, nombre, mime, contenido, privado(request)["nombre"]
        )
        return fichadoc(doc, True)


@router.get("/documentos/{did}")
def documento(did: int, request: Request):
    with obtener_sesion(request.app.state.motor) as s:
        return fichadoc(buscar(s, Documento, did), True)


@router.get("/documentos/{did}/archivo")
def descargar(did: int, request: Request):
    with transaccion(request.app.state.motor) as s:
        d = buscar(s, Documento, did)
        registrar(
            s,
            buscar(s, Convocatoria, d.convocatoria_id),
            privado(request)["nombre"],
            "descarga",
            d.nombre,
            d.postulante_id,
            d.id,
        )
        return Response(
            d.contenido,
            media_type=d.mime,
            headers={
                "Content-Disposition": "attachment; filename*=UTF-8''"
                + quote(d.nombre, safe=""),
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-store",
                "Content-Security-Policy": "sandbox; default-src 'none'",
            },
        )


@router.post("/documentos/{did}/analizar")
def analizar(did: int, request: Request):
    motor = request.app.state.motor
    with obtener_sesion(motor) as s:
        d = buscar(s, Documento, did)
        if d.estado not in ("recibido", "error_lectura"):
            return fichadoc(d, True)
        nombre, contenido, revision = d.nombre, d.contenido, d.revision
    resultado = analizar_aislado(nombre, contenido)
    with transaccion(motor) as s:
        d = buscar(s, Documento, did)
        if d.revision == revision:
            for clave, valor in resultado.items():
                setattr(d, clave, valor)
            d.revision += 1
            registrar(
                s,
                buscar(s, Convocatoria, d.convocatoria_id),
                privado(request)["nombre"],
                "analisis",
                d.estado,
                d.postulante_id,
                d.id,
            )
        return fichadoc(d, True)


@router.post("/documentos/{did}/validar")
def validar(did: int, request: Request, datos: Correccion):
    with transaccion(request.app.state.motor) as s:
        d = buscar(s, Documento, did)
        c = buscar(s, Convocatoria, d.convocatoria_id)
        if c.estado in ("resultado_registrado", "cancelada"):
            raise HTTPException(409, "La revisión ha concluido.")
        if d.revision != datos.revision:
            raise HTTPException(409, "La extracción cambió. Actualice la ficha.")
        campos = list(d.campos)
        if datos.indice >= len(campos):
            raise HTTPException(404, "El campo indicado no existe.")
        original = campos[datos.indice]
        if datos.estado == "corregido" and not datos.valor:
            raise HTTPException(422, "Indique el valor corregido.")
        if datos.estado == "corregido" and original["campo"] in (
            "oferta",
            "ingresos",
            "costos",
        ):
            from services.trazadocs import soles

            try:
                efectivo = str(soles(datos.valor))
            except ValueError as e:
                raise HTTPException(422, str(e)) from e
        elif datos.estado == "corregido":
            efectivo = datos.valor
        elif datos.estado == "confirmado":
            efectivo = original.get("efectivo") or original["valor"]
        else:
            efectivo = None
        campos[datos.indice] = {
            **original,
            "estado": datos.estado,
            "efectivo": efectivo,
        }
        registrar(
            s,
            c,
            privado(request)["nombre"],
            "validacion_documental",
            datos.motivo,
            d.postulante_id,
            d.id,
            {
                "indice": datos.indice,
                "anterior": original,
                "nuevo": campos[datos.indice],
            },
        )
        d.campos = campos
        d.revision += 1
        return fichadoc(d, True)


@router.get("/convocatorias/{cid}/comparar")
def comparador(cid: int, request: Request, ids: str = Query("", max_length=100)):
    elegidos = []
    if ids:
        try:
            elegidos = list(dict.fromkeys(int(i) for i in ids.split(",")))
        except ValueError as e:
            raise HTTPException(422, "Seleccione identificadores numéricos.") from e
        if len(elegidos) > 5:
            raise HTTPException(422, "Seleccione hasta cinco postulantes.")
    with obtener_sesion(request.app.state.motor) as s:
        c = buscar(s, Convocatoria, cid)
        todos = lista_postulantes(s, c)
        postulantes = [p for p in todos if not elegidos or p["id"] in elegidos]
        if elegidos and len(postulantes) != len(elegidos):
            raise HTTPException(404, "Selección ajena a la convocatoria.")
        return dict(
            items=[
                {
                    **comparar(s, c, p),
                    **calificaciones(s, c, p["id"], privado(request)["usuario"]),
                }
                for p in postulantes[:5]
            ],
            total=len(todos),
            version=c.version_bases,
        )


@router.post("/convocatorias/{cid}/revision")
def revisar(cid: int, request: Request, datos: Revision):
    with transaccion(request.app.state.motor) as s:
        c = buscar(s, Convocatoria, cid)
        if c.estado in ("borrador", "resultado_registrado", "cancelada"):
            raise HTTPException(409, "El estado no admite revisión.")
        if datos.postulante_id:
            postulante_local(s, c, datos.postulante_id)
        registrar(
            s,
            c,
            privado(request)["nombre"],
            "revision",
            datos.motivo,
            datos.postulante_id,
        )
        return detalle(s, c)


@router.post("/convocatorias/{cid}/estado")
def cambiar_estado(cid: int, request: Request, datos: Transicion):
    transiciones = {
        "borrador": {"abierta", "cancelada"},
        "abierta": {"cerrada", "cancelada"},
        "cerrada": {"en_evaluacion", "cancelada"},
        "en_evaluacion": {"resultado_registrado", "cancelada"},
    }
    with transaccion(request.app.state.motor) as s:
        c = buscar(s, Convocatoria, cid)
        comprobar_version(datos.version, c)
        if datos.estado not in transiciones.get(c.estado, set()):
            raise HTTPException(409, "Transición de estado no admitida.")
        if datos.estado == "abierta" and not s.scalar(
            select(Documento.id).where(
                Documento.convocatoria_id == cid, Documento.tipo == "bases"
            )
        ):
            raise HTTPException(409, "Adjunte las bases antes de abrir el registro.")
        autor = privado(request)["nombre"]
        if datos.estado == "resultado_registrado":
            if not datos.postulante_id:
                raise HTTPException(
                    422, "Seleccione el postulante del resultado ficticio."
                )
            p = postulante_local(s, c, datos.postulante_id)
            historial = admisiones(s, p.id)
            if historial and historial[-1]["estado"] == "no_admitida":
                raise HTTPException(409, "No se puede seleccionar a un postulante no admitido.")
            alcance = (
                EventoConvocatoria.convocatoria_id == cid,
                or_(
                    EventoConvocatoria.postulante_id == p.id,
                    EventoConvocatoria.postulante_id.is_(None),
                ),
            )
            ultima_revision = s.scalar(
                select(func.max(EventoConvocatoria.id)).where(
                    *alcance, EventoConvocatoria.accion == "revision"
                )
            )
            ultimo_cambio = s.scalar(
                select(func.max(EventoConvocatoria.id)).where(
                    *alcance,
                    EventoConvocatoria.accion.in_(
                        [
                            "carga_documental",
                            "analisis",
                            "validacion_documental",
                            "evaluacion_individual",
                        ]
                    ),
                )
            )
            if not ultima_revision or (
                ultimo_cambio and ultima_revision < ultimo_cambio
            ):
                raise HTTPException(
                    409,
                    "Registre una revisión humana posterior a la última evidencia o calificación.",
                )
            concesion_id = None
            if "concesion" in normal(c.modalidad):
                from services.concesiones import abrir_concesion

                inicio = c.cierre + timedelta(days=1)
                mes = inicio.month - 1 + c.duracion_meses
                anio = inicio.year + mes // 12
                mes = mes % 12 + 1
                fin = date(
                    anio, mes, min(inicio.day, monthrange(anio, mes)[1])
                ) - timedelta(days=1)
                ruc = buscar(s, Proveedor, p.proveedor_id).ruc
                concesion_id = abrir_concesion(
                    s,
                    c.id,
                    c.codigo,
                    c.ubicacion or c.nombre,
                    c.area,
                    ruc,
                    p.oferta,
                    inicio,
                    fin,
                )
            c.resultado = dict(
                postulante_id=p.id,
                motivo=datos.motivo,
                autor=autor,
                concesion_id=concesion_id,
                version_bases=c.version_bases,
            )
        elif datos.postulante_id:
            raise HTTPException(
                422, "Solo el registro de resultado selecciona un postulante."
            )
        c.estado = datos.estado
        c.version += 1
        registrar(
            s,
            c,
            autor,
            c.estado,
            datos.motivo,
            datos.postulante_id,
            datos={"version": c.version, "bases": c.version_bases},
        )
        return detalle(s, c)


# Escenario sintético de coincidencias: un miembro del comité con el mismo nombre que un
# representante, un apellido compartido, dos postulantes con el mismo domicilio y un vínculo
# documentado. Todos los nombres son ficticios.
INTERVINIENTES_DEMO = (
    dict(nombre="Evaluadora Lumen (demo)", rol="Comité"),
    dict(nombre="Supervisor Ámbar (demo)", rol="Supervisión"),
    dict(nombre="Diego Salazar Ríos (demo)", rol="Comité de selección"),
)
DATOS_DEMO = {
    "00900000001": ("Av. España 1240, Trujillo (demo)", "Diego Salazar Ríos (demo)"),
    "00900000002": ("Jr. Pizarro 455, Trujillo (demo)", "Rosa Lumen Castillo (demo)"),
    "00900000003": ("Jr. Pizarro 455, Trujillo (demo)", "Martín Quispe Arana (demo)"),
}
SEMILLA_ANTERIOR = {
    "00900000001": ("Campus Norte (demo)", "Representante Aurora (demo)"),
    "00900000002": ("Campus Norte (demo)", "Representante Horizonte (demo)"),
    "00900000003": ("Campus Norte (demo)", "Representante Nova (demo)"),
}


def actualizar_escenario_cafeteria(motor):
    """Migra la base de demostración distribuida al escenario de coincidencias.

    Solo modifica valores que aún conservan la semilla original; nunca sobrescribe ediciones.
    """
    with transaccion(motor) as s:
        cambios = []
        for ruc, (domicilio, representante) in DATOS_DEMO.items():
            v = s.scalar(select(Proveedor).where(Proveedor.ruc == ruc))
            if v and (v.domicilio, v.representante) == SEMILLA_ANTERIOR[ruc]:
                v.domicilio, v.representante = domicilio, representante
                cambios.append(v.razon_social)
        c = s.scalar(select(Convocatoria).where(Convocatoria.codigo == "CAF-DEMO-001"))
        if c:
            nombres = {normal(i["nombre"]) for i in c.intervinientes}
            faltan = [dict(i) for i in INTERVINIENTES_DEMO if normal(i["nombre"]) not in nombres]
            if faltan:
                c.intervinientes = [*c.intervinientes, *faltan]
                cambios.append("intervinientes")
            if cambios:
                registrar(s, c, "Generador de demostración", "ajuste_demo",
                          "Escenario sintético de coincidencias para revisión.", datos={"cambios": cambios})
            detectar_convocatoria(s, c)


def sembrar_cafeteria(motor):
    """Inicializa únicamente el escenario ficticio. Nunca reescribe decisiones existentes."""
    from services.trazadocs import extraer

    with transaccion(motor) as s:
        if s.scalar(
            select(Convocatoria.id).where(Convocatoria.codigo == "CAF-DEMO-001")
        ):
            return
        c = Convocatoria(
            codigo="CAF-DEMO-001",
            nombre="Concesión de servicio de cafetería universitaria",
            modalidad="Concesión de espacios",
            area="Gestión patrimonial (demo)",
            objeto="Operación de la cafetería del Pabellón Norte",
            descripcion="Recepción interna de propuestas de servicio.",
            presupuesto=4000,
            duracion_meses=12,
            apertura=date(2026, 11, 15),
            cierre=date(2026, 11, 30),
            responsable="Coordinación Patrimonial (demo)",
            ubicacion="Pabellón Norte (demo)",
            requisitos=["RUC", "Experiencia", "Plan operativo", "Garantía"],
            criterios=[
                dict(nombre=n, peso=p)
                for n, p in [
                    ("Propuesta operativa", 30),
                    ("Experiencia", 20),
                    ("Mantenimiento y calidad", 15),
                    ("Sostenibilidad y atención", 10),
                    ("Contraprestación ofrecida", 25),
                ]
            ],
            intervinientes=[dict(i) for i in INTERVINIENTES_DEMO],
            estado="abierta",
        )
        s.add(c)
        s.flush()
        instante = datetime(2026, 11, 18, 15)

        def incorporar(pid, tipo, nombre):
            raw = (CARPETA_DEMO / nombre).read_bytes()
            doc = guardar_archivo(
                s, c, pid, tipo, nombre, None, raw, "Generador de demostración"
            )
            doc.fecha = instante
            for k, v in extraer(Path(nombre).suffix, raw).items():
                setattr(doc, k, v)

        incorporar(None, "bases", "bases-cafeteria.pdf")
        for num, (slug, nombre, monto, experiencia) in enumerate(
            [
                ("aurora", "Servicios Campus Aurora (demo)", 4200, 7),
                ("horizonte", "Operaciones Horizonte (demo)", 4950, 3),
                ("nova", "Gestión Nova Campus (demo)", 4400, 5),
            ],
            1,
        ):
            ruc = f"0090000000{num}"
            proveedor = s.scalar(select(Proveedor).where(Proveedor.ruc == ruc))
            if proveedor is None:
                proveedor = Proveedor(
                    ruc=ruc,
                    razon_social=nombre,
                    fecha_constitucion=date(2011 + num, 1, 1),
                    domicilio=DATOS_DEMO[ruc][0],
                    representante=DATOS_DEMO[ruc][1],
                )
                s.add(proveedor)
                s.flush()
            if proveedor.razon_social != nombre:
                raise RuntimeError(
                    "El RUC reservado del escenario pertenece a un registro ajeno a la demo."
                )
            p = Postulacion(
                convocatoria_id=c.id,
                proveedor_id=proveedor.id,
                oferta=monto,
                experiencia=experiencia,
                fecha=instante,
                version_bases=c.version_bases,
            )
            s.add(p)
            s.flush()
            for tipo, sufijo in [
                ("propuesta", "oferta.pdf"),
                ("propuesta", "plan.docx"),
                ("anexo", "anexo.xlsx"),
            ]:
                incorporar(p.id, tipo, f"{slug}-{sufijo}")
        registrar(
            s,
            c,
            "Generador de demostración",
            "apertura_simulada",
            "Inicio de la recepción interna del caso de cafetería.",
        )
        for evento in list(s.new):
            if isinstance(evento, EventoConvocatoria):
                evento.fecha = instante
        for evento in s.scalars(
            select(EventoConvocatoria).where(EventoConvocatoria.convocatoria_id == c.id)
        ):
            evento.fecha = instante


class Evaluacion(Revision):
    postulante_id: int = Field(gt=0)
    criterio: Texto
    puntaje: Decimal = Field(ge=0, le=100, decimal_places=2)
    documento_id: int = Field(gt=0)
    ubicacion: Texto


@router.post("/convocatorias/{cid}/evaluaciones", status_code=201)
def evaluar(cid: int, request: Request, datos: Evaluacion):
    from db.convocatorias import NotaCriterio

    with transaccion(request.app.state.motor) as s:
        c = buscar(s, Convocatoria, cid)
        if c.estado != "en_evaluacion":
            raise HTTPException(
                409, "La calificación requiere una convocatoria en evaluación."
            )
        p = postulante_local(s, c, datos.postulante_id)
        d = buscar(s, Documento, datos.documento_id)
        if d.postulante_id != p.id or d.convocatoria_id != cid:
            raise HTTPException(422, "La evidencia debe pertenecer al postulante.")
        if datos.criterio not in [k["nombre"] for k in c.criterios]:
            raise HTTPException(422, "El criterio no pertenece a las bases congeladas.")
        user = privado(request)
        nota = NotaCriterio(
            **datos.model_dump(), autor=user["usuario"], version_bases=c.version_bases
        )
        s.add(nota)
        s.flush()
        registrar(
            s,
            c,
            user["nombre"],
            "evaluacion_individual",
            "Se guardó una versión de la evaluación individual.",
            p.id,
            d.id,
            {"evaluacion_id": nota.id},
        )
        return dict(id=nota.id, version_bases=c.version_bases)


@router.post("/convocatorias/{cid}/postulantes/{pid}/admision")
def decidir_admision(cid: int, pid: int, request: Request, datos: DecisionAdmision):
    """La universidad admite, observa o no admite a una empresa. Cada decisión queda en el historial."""
    with transaccion(request.app.state.motor) as s:
        c = buscar(s, Convocatoria, cid)
        if c.estado not in ("abierta", "cerrada", "en_evaluacion"):
            raise HTTPException(409, "La admisión se decide mientras la convocatoria está en curso.")
        p = postulante_local(s, c, pid)
        historial = admisiones(s, p.id)
        if historial and historial[-1]["estado"] == datos.estado and historial[-1]["motivo"] == datos.motivo:
            raise HTTPException(409, "La decisión ya está registrada.")
        autor = privado(request)["nombre"]
        s.add(Admision(postulacion_id=p.id, estado=datos.estado, motivo=datos.motivo, autor=autor))
        registrar(s, c, autor, "admision", f"{ADMISION[datos.estado]}: {datos.motivo}", p.id,
                  datos={"estado": datos.estado})
        s.flush()
        return detalle(s, c)
