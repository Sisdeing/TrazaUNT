"""API de verificación, vínculos y seguimiento patrimonial."""

from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from db.database import obtener_sesion
from db.integridad import (
    Abono,
    Concesion,
    Cuota,
    Declaracion,
    EvaluacionIFP,
    EvidenciaIFP,
    Perfil,
    Vinculo,
)
from db.models import Proveedor
from services.concesiones import ficha_concesion, simular
from services.integridad import CORTE, casos, resultado_ifp
from services.padron import consultar_publico, ruc_valido


def lector(request: Request):
    actor = getattr(request.state, "usuario", None)
    if not actor or actor.get("rol") not in {"analista", "administrador", "consulta"}:
        raise HTTPException(403, "Acceso de detalle reservado a perfiles autorizados.")
    return actor


def analista(actor=Depends(lector)):
    if actor["rol"] not in {"analista", "administrador"}:
        raise HTTPException(403, "Esta acción requiere un perfil de análisis.")
    return actor["usuario"]


def sesion(request: Request):
    with obtener_sesion(request.app.state.motor) as s:
        yield s


# La transacción debe confirmarse antes de responder: si se cerrara después, el registro
# de auditoría (que escribe al terminar la petición) encontraría la base bloqueada.
try:
    SESION = Depends(sesion, scope="function")
except TypeError:  # versiones de FastAPI sin «scope»
    SESION = Depends(sesion)


router = APIRouter(
    prefix="/api",
    dependencies=[Depends(lector)],
    tags=["Proveedores, integridad y patrimonio"],
)


class Entrada(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, allow_inf_nan=False
    )


class Verificacion(Entrada):
    ruc: str = Field(pattern=r"^[0-9]{11}$")
    modo: Literal["demo", "publico"] = "demo"
    categoria: Literal["servicios", "bienes", "obras", "concesiones"] = "servicios"
    monto: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)


class RevisionVinculo(Entrada):
    vinculo_id: int = Field(gt=0)
    accion: Literal[
        "sin conflicto declarado",
        "conflicto declarado",
        "abstención registrada",
        "aclaración solicitada",
        "descargo solicitado",
        "cierre justificado",
    ]
    motivo: str = Field(min_length=8, max_length=1000)


class Simulacion(Entrada):
    ingresos: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    costos: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    contraprestacion: Decimal = Field(ge=0, max_digits=14, decimal_places=2)


class PagoRecibido(Entrada):
    cuota_id: int = Field(gt=0)
    monto: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    fecha: date
    referencia: str = Field(min_length=3, max_length=80)


class VerificacionManual(Entrada):
    dimension: Literal["sanciones", "obligaciones"]
    resultado: bool
    referencia: str = Field(min_length=5, max_length=120)
    corte: date
    vigente_hasta: date


@router.get("/proveedores")
def proveedores(
    q: str = Query("", max_length=160),
    pagina: int = Query(1, ge=1),
    limite: int = Query(25, ge=1, le=100),
    tipo: Literal["jurídica", "natural"] | None = None,
    s=SESION,
):
    consulta = (
        select(Proveedor, Perfil)
        .outerjoin(Perfil, Perfil.proveedor_id == Proveedor.id)
        .where(Proveedor.ruc.startswith("00"))
    )
    if q:
        consulta = consulta.where(
            or_(
                Proveedor.ruc.contains(q, autoescape=True),
                Proveedor.razon_social.contains(q, autoescape=True),
            )
        )
    if tipo:
        consulta = consulta.where(Perfil.tipo == tipo)
    total = s.scalar(select(func.count()).select_from(consulta.subquery()))
    filas = s.execute(
        consulta.order_by(
            Proveedor.ruc.startswith("009000000").desc(),
            Perfil.proveedor_id.is_(None),
            Proveedor.razon_social,
            Proveedor.id,
        )
        .offset((pagina - 1) * limite)
        .limit(limite)
    )
    return dict(
        items=[
            dict(
                id=p.id,
                ruc=p.ruc,
                razon_social=p.razon_social,
                tipo=x.tipo if x else "sin clasificar",
            )
            for p, x in filas
        ],
        total=total,
        pagina=pagina,
    )


def proveedor_demo(s, identificador):
    p = s.get(Proveedor, identificador)
    if p is None or not p.ruc.startswith("00"):
        raise HTTPException(404, "Proveedor de demostración no encontrado.")
    return p


@router.get("/proveedores/{identificador:int}")
def proveedor(identificador: int, s=SESION):
    return resultado_ifp(s, proveedor_demo(s, identificador))


@router.post("/proveedores/verificar")
def verificar(
    datos: Verificacion, request: Request, actor=Depends(analista), s=SESION
):
    if datos.modo == "publico":
        try:
            return consultar_publico(datos.ruc)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
    if not ruc_valido(datos.ruc, demo=True) or not datos.ruc.startswith("00"):
        raise HTTPException(
            422, "En demostración se admiten únicamente RUC sintéticos con prefijo 00."
        )
    p = s.scalar(select(Proveedor).where(Proveedor.ruc == datos.ruc))
    if p is None:
        raise HTTPException(404, "El RUC no figura en el catálogo sintético.")
    r = resultado_ifp(s, p, datos.monto, datos.categoria)
    e = EvaluacionIFP(proveedor_id=p.id, resultado=r, responsable=actor)
    s.add(e)
    s.flush()
    return dict(**r, evaluacion_id=e.id)


@router.get("/proveedores/{identificador:int}/evaluaciones")
def evaluaciones(identificador: int, s=SESION):
    proveedor_demo(s, identificador)
    filas = s.scalars(
        select(EvaluacionIFP)
        .where(EvaluacionIFP.proveedor_id == identificador)
        .order_by(EvaluacionIFP.id.desc())
        .limit(100)
    )
    return dict(
        items=[
            dict(
                id=x.id,
                fecha=x.fecha.isoformat() + "Z",
                responsable=x.responsable,
                resultado=x.resultado,
            )
            for x in filas
        ]
    )


@router.post(
    "/proveedores/{identificador:int}/verificaciones-manuales", status_code=201
)
def verificar_manual(
    identificador: int,
    datos: VerificacionManual,
    actor=Depends(analista),
    s=SESION,
):
    p = proveedor_demo(s, identificador)
    if not s.get(Perfil, p.id):
        raise HTTPException(409, "El proveedor requiere un perfil de evaluación.")
    if datos.corte > CORTE or datos.vigente_hasta < datos.corte:
        raise HTTPException(
            422, "Revise el intervalo de vigencia frente al corte de la demo."
        )
    clave = "vigente" if datos.dimension == "sanciones" else "al_dia"
    fila = EvidenciaIFP(
        proveedor_id=p.id,
        dimension=datos.dimension,
        valores={clave: datos.resultado},
        referencia=datos.referencia,
        origen="simulado",
        fecha=datos.corte,
        vigente_hasta=datos.vigente_hasta,
        responsable=actor,
    )
    s.add(fila)
    try:
        s.flush()
    except IntegrityError as e:
        raise HTTPException(
            409, "La referencia ya está registrada para este proveedor."
        ) from e
    return dict(id=fila.id, estado="Verificación manual registrada en demostración")


@router.get("/conflictos")
def conflictos(s=SESION):
    return dict(items=casos(s), corte=CORTE)


@router.get("/conflictos/{identificador:int}/grafo")
def grafo(identificador: int, s=SESION):
    caso = next((x for x in casos(s) if x["id"] == identificador), None)
    if not caso:
        raise HTTPException(404, "Vinculación no encontrada.")
    nombres = [caso["servidor"], caso["familiar"], caso["proveedor"], caso["proceso"]]
    return dict(
        nodos=[dict(id=i, nombre=n) for i, n in enumerate(nombres)],
        aristas=[
            dict(desde=i, hasta=i + 1, relacion=r)
            for i, r in enumerate([caso["parentesco"], caso["cargo"], "Postula a"])
        ],
        evidencia=caso["evidencia"],
    )


def anotar(datos, s, actor):
    v = s.get(Vinculo, datos.vinculo_id)
    if v is None:
        raise HTTPException(404, "No existe la vinculación.")
    fila = Declaracion(
        vinculo_id=v.id, accion=datos.accion, motivo=datos.motivo, responsable=actor
    )
    s.add(fila)
    s.flush()
    return dict(id=fila.id, accion=fila.accion, responsable=actor)


@router.post("/declaraciones", status_code=201)
def declarar(datos: RevisionVinculo, actor=Depends(analista), s=SESION):
    return anotar(datos, s, actor)


@router.post("/abstenciones", status_code=201)
def abstener(datos: RevisionVinculo, actor=Depends(analista), s=SESION):
    if datos.accion != "abstención registrada":
        raise HTTPException(422, "La acción debe registrar una abstención.")
    return anotar(datos, s, actor)


@router.get("/concesiones")
def concesiones(s=SESION):
    return dict(
        items=[
            ficha_concesion(s, c, CORTE, False)
            for c in s.scalars(select(Concesion).order_by(Concesion.id.desc()))
        ],
        corte=CORTE,
    )


def buscar_concesion(s, identificador):
    c = s.get(Concesion, identificador)
    if c is None:
        raise HTTPException(404, "Concesión no encontrada.")
    return c


@router.get("/concesiones/{identificador:int}")
def concesion(identificador: int, s=SESION):
    return ficha_concesion(s, buscar_concesion(s, identificador), CORTE)


@router.get("/concesiones/{identificador:int}/obligaciones")
def obligaciones(identificador: int, s=SESION):
    return {
        "items": ficha_concesion(s, buscar_concesion(s, identificador), CORTE)[
            "obligaciones"
        ]
    }


@router.post("/concesiones/{identificador:int}/simular")
def escenario(identificador: int, datos: Simulacion, s=SESION):
    buscar_concesion(s, identificador)
    return simular(datos.ingresos, datos.costos, datos.contraprestacion)


@router.post("/concesiones/{identificador:int}/pagos", status_code=201)
def abonar(
    identificador: int, datos: PagoRecibido, actor=Depends(analista), s=SESION
):
    if s.bind.dialect.name == "sqlite":
        s.connection().exec_driver_sql("BEGIN IMMEDIATE")
    c = buscar_concesion(s, identificador)
    cuota = s.scalar(
        select(Cuota)
        .where(Cuota.id == datos.cuota_id, Cuota.concesion_id == c.id)
        .with_for_update()
    )
    if cuota is None:
        raise HTTPException(404, "Cuota no encontrada en la concesión.")
    if datos.fecha < c.inicio or datos.fecha > CORTE:
        raise HTTPException(422, "El abono debe corresponder al periodo observado.")
    pagado = s.scalar(
        select(func.sum(Abono.monto)).where(Abono.cuota_id == cuota.id)
    ) or Decimal(0)
    if datos.monto + pagado > cuota.exigible:
        raise HTTPException(409, "El importe supera el saldo pendiente de esta cuota.")
    a = Abono(
        cuota_id=cuota.id,
        fecha=datos.fecha,
        monto=datos.monto,
        referencia=datos.referencia,
        responsable=actor,
    )
    s.add(a)
    try:
        s.flush()
    except IntegrityError as e:
        raise HTTPException(
            409, "La referencia de abono ya figura en esta cuota."
        ) from e
    return dict(id=a.id, referencia=a.referencia)
