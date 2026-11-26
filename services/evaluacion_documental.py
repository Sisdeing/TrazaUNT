"""Compara observaciones con propuesta y bases sin emitir una adjudicación."""

from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from functools import lru_cache
import yaml
from sqlalchemy import select
from db.convocatorias import Documento
from services.trazadocs import normal


@lru_cache(maxsize=1)
def parametros():
    ruta = Path(__file__).resolve().parents[1] / "config/documentos.yaml"
    with ruta.open(encoding="utf8") as archivo:
        return yaml.safe_load(archivo)


def documentos_vigentes(s, cid, pid):
    docs = s.scalars(
        select(Documento)
        .where(Documento.convocatoria_id == cid, Documento.postulante_id == pid)
        .order_by(Documento.id.desc())
    )
    ultimos = {}
    for d in docs:
        ultimos.setdefault(d.nombre, d)
    return list(ultimos.values())


def comparar(s, c, p):
    from services.integridad import resumen_ifp, senales_proveedor

    docs = documentos_vigentes(s, c.id, p["id"])
    campos = [(d, k) for d in docs for k in d.campos if k["estado"] != "descartado"]
    requisitos = []
    alertas = []
    cfg = parametros()
    tolerancia = Decimal(str(cfg["tolerancia_soles"]))

    def aviso(regla, motivo, doc=None, ubicacion=None):
        filtro = cfg["reglas"][regla]
        alertas.append(
            dict(
                regla=regla,
                explicacion=motivo,
                documento_id=doc.id if doc else None,
                ubicacion=ubicacion,
                severidad=filtro["severidad"],
                certeza="indicio",
                accion=filtro["accion"],
                estado="pendiente_revision",
                base_legal="verificar",
            )
        )

    def valor(k):
        return k.get("efectivo") or k["valor"]

    for req in c.requisitos:
        clave = normal(req)
        encontrado = next(
            (
                (d, k)
                for d, k in campos
                if normal(k["campo"].replace("_", " ")) == clave
            ),
            None,
        )
        if encontrado:
            doc, k = encontrado
            estado = (
                "Confirmado por el analista"
                if k["estado"] in ("confirmado", "corregido")
                else "Evidencia encontrada"
            )
            requisitos.append(
                dict(
                    requisito=req,
                    estado=estado,
                    documento_id=doc.id,
                    ubicacion=k["ubicacion"],
                    fragmento=k["fragmento"],
                )
            )
        else:
            procesados = bool(docs) and all(
                d.estado in ("analizado", "requiere_revision") for d in docs
            )
            estado = "No localizada" if procesados else "Pendiente de revisión"
            requisitos.append(
                dict(requisito=req, estado=estado, documento_id=None, ubicacion=None)
            )
            if procesados:
                aviso(
                    "D01",
                    f"Requisito «{req}»: no se localizó evidencia etiquetada en la última versión de los documentos.",
                )
    ingresos, costos = [], []
    for d, k in campos:
        campo = k["campo"]
        texto = valor(k)
        if campo == "ruc" and texto != p["ruc"]:
            aviso(
                "D02",
                f"El RUC extraído ({texto}) difiere del registrado ({p['ruc']}).",
                d,
                k["ubicacion"],
            )
        elif campo == "razon_social" and normal(texto) != normal(p["razon_social"]):
            aviso(
                "D02",
                "La razón social extraída difiere del nombre registrado.",
                d,
                k["ubicacion"],
            )
        elif campo == "oferta":
            if abs(Decimal(texto) - Decimal(str(p["oferta"]))) > tolerancia:
                aviso(
                    "D03",
                    f"El documento indica S/ {texto} y la oferta registrada es S/ {p['oferta']:.2f}.",
                    d,
                    k["ubicacion"],
                )
        elif campo == "vigencia_garantia":
            try:
                if date.fromisoformat(texto) < c.cierre:
                    aviso(
                        "D09",
                        "La fecha de vigencia declarada es anterior al cierre de recepción.",
                        d,
                        k["ubicacion"],
                    )
            except ValueError:
                aviso(
                    "D09",
                    "El formato de fecha de la garantía requiere verificación manual.",
                    d,
                    k["ubicacion"],
                )
        elif campo == "ingresos":
            ingresos.append((d, Decimal(texto)))
        elif campo == "costos":
            costos.append((d, Decimal(texto)))
    for d in docs:
        if d.tipo != "propuesta":
            continue
        otro = s.scalar(
            select(Documento.id).where(
                Documento.convocatoria_id == c.id,
                Documento.postulante_id != p["id"],
                Documento.sha256 == d.sha256,
                Documento.tipo == "propuesta",
            )
        )
        if otro:
            aviso(
                "D05",
                "La propuesta coincide byte por byte con la de otro postulante. Verifique si se trata de un formato común.",
                d,
            )
    indicador = None
    patrimonial = any(
        t in normal(c.modalidad) for t in ("concesion", "arrendamiento", "explotacion")
    )
    for d, i in ingresos if patrimonial else []:
        coste = next((v for fuente, v in costos if fuente.id == d.id), None)
        if coste is not None:
            saldo = i - coste - Decimal(str(p["oferta"]))
            indicador = dict(
                nombre="Saldo operativo mensual declarado",
                valor=float(saldo),
                documento_id=d.id,
                explicacion="Ingresos menos costos menos contraprestación registrada. Indicador preventivo del escenario declarado.",
            )
            break
    return {
        **p,
        **resumen_ifp(
            s,
            p["ruc"],
            monto=p["oferta"],
            categoria="concesiones"
            if patrimonial
            else {"bienes": "bienes", "obras": "obras"}.get(
                normal(c.modalidad), "servicios"
            ),
        ),
        "requisitos": requisitos,
        "alertas": alertas,
        "documentos": len(docs),
        "vinculaciones": senales_proveedor(s, c.codigo, p["ruc"]),
        "indicador_preventivo": indicador,
        "puntaje_preliminar": None,
    }


def calificaciones(s, c, pid, autor):
    from db.convocatorias import NotaCriterio

    notas = s.scalars(
        select(NotaCriterio)
        .where(
            NotaCriterio.postulante_id == pid,
            NotaCriterio.version_bases == c.version_bases,
            NotaCriterio.autor == autor,
        )
        .order_by(NotaCriterio.id.desc())
    )
    por_criterio = {}
    for nota in notas:
        por_criterio.setdefault(nota.criterio, nota)
    criterios = []
    for k in c.criterios:
        nota = por_criterio.get(k["nombre"])
        criterios.append(
            dict(
                **k,
                puntaje=float(nota.puntaje) if nota else None,
                documento_id=nota.documento_id if nota else None,
                ubicacion=nota.ubicacion if nota else None,
            )
        )
    total = None
    if all(k["puntaje"] is not None for k in criterios):
        total = round(sum(k["puntaje"] * k["peso"] / 100 for k in criterios), 2)
    return dict(criterios=criterios, puntaje_preliminar=total)
