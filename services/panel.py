"""Indicadores descriptivos y navegación sobre la base sintética."""

from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, or_, select

from db.convocatorias import Convocatoria
from db.database import obtener_sesion
from db.integridad import Concesion, Obligacion, EvaluacionIFP, Vinculo
from db.models import Alerta, Contratacion as C, Entidad, Proveedor
from services.seguridad import Acceso

router = APIRouter(prefix="/api", tags=["Inteligencia institucional"])
CORTE = date(2026, 11, 23)


def periodo_fecha(fecha):
    return f"{fecha.year}-S{1 if fecha.month <= 6 else 2}"


@router.get("/dashboard")
@router.get("/inteligencia-economica")
def dashboard(
    request: Request,
    periodo: str = Query("", max_length=8),
    entidad: int | None = Query(None, gt=0),
    categoria: str = Query("", max_length=300),
    tipo: str = Query("", max_length=100),
    estado: Literal["", "pendiente", "confirmada", "descartada"] = "",
    severidad: Literal["", "alta", "media", "baja"] = "",
):
    with obtener_sesion(request.app.state.motor) as s:
        base = select(
            C.id,
            C.codigo,
            C.fecha,
            C.objeto,
            C.entidad_id,
            C.monto,
            C.proveedor_id,
            Proveedor.razon_social,
            C.tipo_proceso,
            C.n_postores,
        ).join(Proveedor)
        universo = s.execute(base.order_by(C.fecha)).all()
        opciones = dict(
            periodos=sorted({periodo_fecha(x.fecha) for x in universo}),
            categorias=sorted({x.objeto for x in universo}),
            tipos=sorted({x.tipo_proceso for x in universo}),
        )
        seleccion = {
            x.id: x
            for x in universo
            if (not periodo or periodo_fecha(x.fecha) == periodo)
            and (not entidad or entidad == x.entidad_id)
            and (not categoria or x.objeto == categoria)
            and (not tipo or x.tipo_proceso == tipo)
        }
        consulta = select(
            Alerta.id,
            Alerta.contratacion_id,
            Alerta.severidad,
            Alerta.estado,
            Alerta.regla_id,
            Alerta.score,
        ).where(
            or_(
                Alerta.evidencia_json["_vigente"].as_boolean().is_(None),
                Alerta.evidencia_json["_vigente"].as_boolean().is_(True),
            )
        )
        if estado:
            consulta = consulta.where(Alerta.estado == estado)
        if severidad:
            consulta = consulta.where(Alerta.severidad == severidad)
        alertas = [
            a
            for a in s.execute(consulta.order_by(Alerta.score.desc(), Alerta.id))
            if a.contratacion_id in seleccion
        ]
        if estado or severidad:
            afectados = {a.contratacion_id for a in alertas}
            seleccion = {k: v for k, v in seleccion.items() if k in afectados}
        procesos = s.execute(
            select(
                Convocatoria.id,
                Convocatoria.codigo,
                Convocatoria.nombre,
                Convocatoria.estado,
            ).order_by(Convocatoria.id)
        ).all()
        cafeteria = next((c for c in procesos if "cafetería" in c.nombre.lower()), None)
        cartera = dict(
            abiertas=sum(
                c.estado in ("abierta", "recepcion", "abierta_para_registro")
                for c in procesos
            ),
            evaluados=s.scalar(
                select(func.count(func.distinct(EvaluacionIFP.proveedor_id)))
            ),
            concesiones=s.scalar(
                select(func.count(Concesion.id)).where(
                    Concesion.inicio <= CORTE, Concesion.fin >= CORTE
                )
            ),
            proximas=s.scalar(
                select(func.count(Obligacion.id)).where(
                    Obligacion.vence >= CORTE,
                    Obligacion.vence <= CORTE + timedelta(days=30),
                    Obligacion.cumplida.is_(None),
                )
            ),
            vinculaciones=s.scalar(
                select(func.count(Vinculo.id)).where(
                    Vinculo.verificado.is_(True),
                    Vinculo.desde <= CORTE,
                    or_(Vinculo.hasta.is_(None), Vinculo.hasta >= CORTE),
                )
            ),
        )
        areas = dict(s.execute(select(Entidad.id, Entidad.nombre)).all())
        from db.coincidencias import Coincidencia
        from db.trazabilidad import AlertaTZ, Expediente
        coincidencias = Counter(
            s.scalars(select(Coincidencia.nivel).where(Coincidencia.vigente.is_(True), Coincidencia.estado == "pendiente"))
        )
        cartera["coincidencias"] = sum(coincidencias.values())
        cartera["expedientes"] = s.scalar(select(func.count(Expediente.id)))
        cartera["alertas_tz"] = s.scalar(
            select(func.count(AlertaTZ.id)).where(AlertaTZ.vigente.is_(True), AlertaTZ.estado == "pendiente")
        )

    montos = defaultdict(Decimal)
    nombres = {}
    meses = {}
    for x in seleccion.values():
        montos[x.proveedor_id] += x.monto
        nombres[x.proveedor_id] = x.razon_social
    fechas = [
        x.fecha for x in universo if not periodo or periodo_fecha(x.fecha) == periodo
    ]
    if fechas:
        mes = min(fechas).replace(day=1)
        while mes <= max(fechas):
            meses[mes.strftime("%Y-%m")] = dict(
                mes=mes.strftime("%Y-%m"), monto=Decimal(0), alta=0, media=0, baja=0
            )
            mes = (mes.replace(day=28) + timedelta(days=4)).replace(day=1)
    for x in seleccion.values():
        meses[x.fecha.strftime("%Y-%m")]["monto"] += x.monto
    por_area = Counter()
    for a in alertas:
        x = seleccion[a.contratacion_id]
        meses[x.fecha.strftime("%Y-%m")][a.severidad] += 1
        por_area[areas[x.entidad_id]] += 1
    total = sum(montos.values(), Decimal(0))
    top = sorted(montos, key=montos.get, reverse=True)
    participaciones = (
        {p: float(v / total * 100) for p, v in montos.items()} if total else {}
    )
    pendientes = [a for a in alertas if a.estado == "pendiente"]
    auditor = request.state.usuario["rol"] == "auditor"
    return dict(
        contrataciones=len(seleccion),
        monto=float(total),
        proveedores=len(montos),
        alertas=len(alertas),
        pendientes=len(pendientes),
        contratos_con_alerta=len({a.contratacion_id for a in alertas}),
        severidades=Counter(a.severidad for a in alertas),
        serie=list(meses.values()),
        opciones=opciones,
        areas=por_area.most_common(),
        cartera=cartera,
        coincidencias=dict(alta=coincidencias["alta"], media=coincidencias["media"], baja=coincidencias["baja"]),
        corte=CORTE,
        concentracion=dict(
            hhi=round(sum(p * p for p in participaciones.values()), 2)
            if total
            else None,
            top5=round(sum(participaciones[p] for p in top[:5]), 2) if total else None,
            un_postor=sum(x.n_postores == 1 for x in seleccion.values()),
            ranking=[]
            if auditor
            else [
                dict(
                    id=p,
                    nombre=nombres[p],
                    monto=montos[p],
                    cuota=round(participaciones[p], 2),
                )
                for p in top[:8]
            ],
        ),
        escenario=None
        if request.state.usuario["rol"] not in ("administrador", "analista")
        or not cafeteria
        else dict(id=cafeteria.id, codigo=cafeteria.codigo, estado=cafeteria.estado),
        prioritarias=[]
        if auditor
        else [
            dict(
                id=a.id,
                contratacion_id=a.contratacion_id,
                codigo=seleccion[a.contratacion_id].codigo,
                regla=a.regla_id,
                severidad=a.severidad,
                estado=a.estado,
                score=float(a.score),
            )
            for a in pendientes[:5]
        ],
    )


@router.get("/buscar")
def buscar(request: Request, q: str = Query(min_length=2, max_length=150)):
    consulta = q.strip()
    if len(consulta) < 2:
        return {"items": []}
    recursos = [
        (C, C.codigo, C.objeto, "expedientes", "Expediente"),
        (Proveedor, Proveedor.ruc, Proveedor.razon_social, "proveedores", "Proveedor"),
        (
            Convocatoria,
            Convocatoria.codigo,
            Convocatoria.nombre,
            "convocatorias",
            "Convocatoria",
        ),
        (Concesion, Concesion.codigo, Concesion.espacio, "concesiones", "Concesión"),
    ]
    items = []
    with obtener_sesion(request.app.state.motor) as s:
        for modelo, codigo, nombre, ruta, tipo in recursos:
            if ruta == "convocatorias" and request.state.usuario["rol"] == "consulta":
                continue
            stmt = (
                select(modelo.id, codigo, nombre)
                .where(
                    or_(
                        codigo.contains(consulta, autoescape=True),
                        nombre.contains(consulta, autoescape=True),
                    )
                )
                .order_by(modelo.id)
                .limit(5)
            )
            items.extend(
                dict(tipo=tipo, codigo=c, titulo=n, ruta=f"#{ruta}/{i}")
                for i, c, n in s.execute(stmt)
            )
    return {"items": items}


@router.get("/auditoria")
def auditoria(request: Request, pagina: int = Query(1, ge=1)):
    with obtener_sesion(request.app.state.motor) as s:
        rows = s.scalars(
            select(Acceso)
            .order_by(Acceso.id.desc())
            .offset((pagina - 1) * 25)
            .limit(25)
        )
        return dict(
            items=[
                dict(
                    id=a.id,
                    usuario=a.usuario,
                    accion=a.metodo,
                    ruta=a.ruta,
                    estado=a.estado,
                    fecha=a.fecha.isoformat() + "Z",
                )
                for a in rows
            ],
            total=s.scalar(select(func.count(Acceso.id))),
            pagina=pagina,
            tamano=25,
        )


def datos_publicos(s):
    anio = func.strftime("%Y", C.fecha)
    periodos = s.execute(
        select(anio, func.count(C.id), func.sum(C.monto))
        .group_by(anio)
        .order_by(anio.desc())
    ).all()
    tipos = s.execute(
        select(C.tipo_proceso, func.count(C.id), func.sum(C.monto))
        .group_by(C.tipo_proceso)
        .order_by(C.tipo_proceso)
    ).all()
    estados = s.execute(
        select(Convocatoria.estado, func.count(Convocatoria.id))
        .group_by(Convocatoria.estado)
        .order_by(Convocatoria.estado)
    ).all()
    alertas = dict(s.execute(
        select(Alerta.estado, func.count(Alerta.id))
        .where(Alerta.evidencia_json["_vigente"].as_boolean().is_not(False))
        .group_by(Alerta.estado)
    ).all())
    return {
        "origen": "sintetico",
        "periodos": [
            {"anio": periodo, "contrataciones": cantidad, "monto": monto}
            for periodo, cantidad, monto in periodos
        ],
        "tipos": [
            {"tipo": tipo, "contrataciones": cantidad, "monto": monto}
            for tipo, cantidad, monto in tipos
        ],
        "estados": [{"estado": estado, "cantidad": cantidad} for estado, cantidad in estados],
        "alertas_atendidas": alertas.get("confirmada", 0) + alertas.get("descartada", 0),
        "alertas_totales": sum(alertas.values()),
    }


@router.get("/publico/contrataciones")
def contrataciones_publicas(request: Request):
    """Publica únicamente agregados del historial sintético."""
    with obtener_sesion(request.app.state.motor) as s:
        return datos_publicos(s)