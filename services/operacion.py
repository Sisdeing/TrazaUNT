"""Bandeja local y consultas estructuradas con referencias a la evidencia."""

from hashlib import sha256
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import Column, String, or_, select
from sqlalchemy.dialects.sqlite import insert

from db.database import obtener_sesion
from db.models import Alerta, Base, Contratacion
from services.predicciones import Pronostico
from db.convocatorias import Convocatoria
from db.integridad import Concesion
from services.concesiones import ficha_concesion
from services.convocatorias import lista_postulantes
from services.evaluacion_documental import comparar
from services.integridad import casos, CORTE
from services.padron import ORIGEN, RUTA_PADRON

router = APIRouter(prefix="/api", tags=["Revisión y fuentes"])


class LecturaAviso(Base):
    __tablename__ = "lecturas_avisos"
    usuario = Column(String(80), primary_key=True)
    clave = Column(String(64), primary_key=True)


def bandeja(s, usuario, experimentales=False):
    filas = []

    def incluir(familia, codigo, titulo, detalle, enlace, referencia):
        clave = sha256(f"{codigo}|{enlace}|{referencia}|{detalle}".encode()).hexdigest()
        filas.append(
            dict(
                clave=clave,
                familia=familia,
                codigo=codigo,
                titulo=titulo,
                detalle=detalle,
                enlace=enlace,
                referencia=referencia,
            )
        )

    if usuario["rol"] in {"analista", "administrador"}:
        for c in s.scalars(
            select(Convocatoria).where(
                Convocatoria.estado.in_(["abierta", "cerrada", "en_evaluacion"])
            )
        ):
            for p in lista_postulantes(s, c):
                actual = comparar(s, c, p)
                for a in actual["alertas"]:
                    ref = f"{c.codigo} · {p['razon_social']} · {a['ubicacion'] or 'Matriz de requisitos'}"
                    incluir(
                        "Documentos",
                        a["regla"],
                        p["razon_social"],
                        a["explicacion"],
                        f"#convocatorias/{c.id}",
                        ref,
                    )
                saldo = actual["indicador_preventivo"]
                if saldo and saldo["valor"] < 0:
                    incluir(
                        "Prevención",
                        "C10",
                        p["razon_social"],
                        f"Saldo mensual estimado de S/ {saldo['valor']:,.2f} bajo los supuestos declarados.",
                        f"#convocatorias/{c.id}",
                        f"{c.codigo} · Documento {saldo['documento_id']}",
                    )
        for caso in casos(s):
            for a in caso["senales"]:
                incluir(
                    "Integridad",
                    a["regla"],
                    caso["proveedor"],
                    a["motivo"],
                    "#alertas",
                    caso["evidencia"],
                )
    for c in s.scalars(select(Concesion)):
        ficha = ficha_concesion(s, c, CORTE)
        for a in ficha["alertas"]:
            incluir(
                "Patrimonio",
                a["codigo"],
                c.espacio,
                a["motivo"],
                f"#concesiones/{c.id}",
                c.codigo,
            )
    if experimentales:
        ultimas = set()
        for pronostico, c in s.execute(
            select(Pronostico, Concesion).join(Concesion).order_by(Pronostico.id.desc())
        ):
            if c.id in ultimas:
                continue
            ultimas.add(c.id)
            if pronostico.datos["nivel"] == "Revisión prioritaria":
                incluir(
                    "Prevención",
                    "P03",
                    c.espacio,
                    "Predicción experimental de mora. Contraste las cuotas y los abonos al corte.",
                    "#predicciones",
                    f"{c.codigo} · {pronostico.version} · {pronostico.corte}",
                )
    stmt = (
        select(
            Alerta.id,
            Alerta.regla_id,
            Alerta.severidad,
            Contratacion.id,
            Contratacion.codigo,
        )
        .join(Contratacion)
        .where(
            Alerta.estado == "pendiente",
            or_(
                Alerta.evidencia_json["_vigente"].as_boolean().is_(None),
                Alerta.evidencia_json["_vigente"].as_boolean().is_(True),
            ),
        )
    )
    for aid, regla, sev, cid, codigo in s.execute(
        stmt.order_by(Alerta.score.desc(), Alerta.id).limit(12)
    ):
        incluir(
            "Expedientes",
            regla.split("_")[0],
            codigo,
            regla.split("_", 1)[1].replace("_", " ").capitalize()
            + f" · severidad {sev}.",
            f"#expedientes/{cid}",
            f"Alerta {aid}",
        )
    leidas = set(
        s.scalars(
            select(LecturaAviso.clave).where(LecturaAviso.usuario == usuario["usuario"])
        )
    )
    return [dict(**f, leida=f["clave"] in leidas) for f in filas]


@router.get("/notificaciones")
def avisos(request: Request):
    with obtener_sesion(request.app.state.motor) as s:
        return {"items": bandeja(s, request.state.usuario, request.app.state.experimentales), "corte": CORTE}


@router.post("/notificaciones/{clave}/leer")
def leer(clave: str, request: Request):
    with obtener_sesion(request.app.state.motor) as s:
        usuario = request.state.usuario
        if not any(x["clave"] == clave for x in bandeja(s, usuario, request.app.state.experimentales)):
            raise HTTPException(404, "Aviso no disponible para este perfil.")
        s.execute(
            insert(LecturaAviso)
            .values(usuario=usuario["usuario"], clave=clave)
            .on_conflict_do_nothing()
        )
    return {"leida": True}


@router.get("/asistente")
def asistente(
    request: Request,
    tema: Literal[
        "Documentos", "Patrimonio", "Integridad", "Prevención", "Expedientes"
    ],
):
    if request.state.usuario["rol"] not in {"analista", "administrador"}:
        raise HTTPException(403, "Se requiere acceso de análisis.")
    with obtener_sesion(request.app.state.motor) as s:
        filas = [x for x in bandeja(s, request.state.usuario, request.app.state.experimentales) if x["familia"] == tema]
    return dict(items=filas, corte=CORTE)


@router.get("/fuentes")
def fuentes():
    return {
        "items": [
            dict(
                nombre="Datos sintéticos TrazaUNT",
                tipo="Simulada",
                estado="Disponible",
                detalle="Semilla 42. Expedientes históricos y escenario de cafetería.",
                url=None,
            ),
            dict(
                nombre="Padrón reducido del RUC",
                tipo="Archivo local autorizado",
                estado="Archivo importado"
                if RUTA_PADRON.exists()
                else "Sin archivo importado",
                detalle="Consulta selectiva de personas jurídicas. Fecha de corte por registro.",
                url=ORIGEN,
            ),
            dict(
                nombre="Sanciones y obligaciones",
                tipo="Revisión manual en demo",
                estado="Disponible",
                detalle="Registra referencia, corte y vigencia desde la ficha del proveedor.",
                url=None,
            ),
        ]
    }
