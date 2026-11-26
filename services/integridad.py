"""Evaluación explicable y señales preventivas sobre evidencia sintética fechada."""

from datetime import date
from functools import lru_cache
from pathlib import Path
import random

import yaml
from sqlalchemy import select

from db.database import obtener_sesion
from db.integridad import Declaracion, EvidenciaIFP, Interviniente, Perfil, Vinculo
from db.models import Proveedor
from services.concesiones import abrir_concesion, sembrar_concesiones

CORTE = date(2026, 11, 23)
AURORA, HORIZONTE, NOVA = ("00900000001", "00900000002", "00900000003")
CAFETERIA = "CAF-DEMO-001"
ETIQUETAS = {
    "registro": "Situación registral",
    "sanciones": "Sanciones administrativas",
    "solvencia": "Capacidad económica",
    "obligaciones": "Obligaciones tributarias y laborales",
    "litigios": "Litigiosidad verificada",
    "historial": "Historial contractual",
    "integridad": "Integridad y vinculaciones",
}
NATURAL = {"registro", "sanciones", "obligaciones", "historial", "integridad"}


@lru_cache(maxsize=1)
def config():
    archivo = Path(__file__).resolve().parents[1] / "config" / "fiabilidad.yaml"
    datos = yaml.safe_load(archivo.read_text(encoding="utf8"))
    for pesos in datos["perfiles"].values():
        if (
            set(pesos) != set(ETIQUETAS)
            or sum(pesos.values()) != 100
            or min(pesos.values()) < 0
        ):
            raise ValueError("Los siete pesos de cada perfil deben sumar 100.")
    return datos


def dato_puntaje(dimension, datos, monto):
    """Sólo los campos comprobados por la fuente participan en el cálculo."""
    if dimension == "registro":
        return (
            int(datos["activo"]) + int(datos["habido"])
        ) / 2, "Estado y condición registral"
    if dimension == "solvencia":
        if not monto:
            return None, "Indique un importe comparable para evaluar capacidad."
        return min(
            1, datos["capacidad"] / float(monto)
        ), "Capacidad disponible / monto referencial"
    if dimension == "historial":
        total = datos["observados"]
        return (
            datos["cumplidos"] / total if total else None
        ), "Contratos cumplidos / contratos observados"
    if dimension == "sanciones":
        return float(
            not datos["vigente"]
        ), "Sanción administrativa vigente en el registro consultado"
    if dimension == "obligaciones":
        return float(
            datos["al_dia"]
        ), "Cumplimiento documentado de las obligaciones aplicables"
    if dimension == "litigios":
        return float(
            not datos["resolucion_firme_adversa"]
        ), "Resolución firme relevante, según expediente revisado"
    return float(
        not datos["incumplimiento_confirmado"]
    ), "Revisión documentada de integridad"


def resultado_ifp(s, proveedor, monto=None, categoria="servicios", corte=CORTE):
    perfil = s.get(Perfil, proveedor.id)
    tipo = perfil.tipo if perfil else "sin clasificar"
    pesos = config()["perfiles"][categoria]
    aplicables = {k: v for k, v in pesos.items() if tipo != "natural" or k in NATURAL}
    # La última verificación sustituye a la anterior aun cuando la nueva esté vencida.
    registros = s.scalars(
        select(EvidenciaIFP)
        .where(EvidenciaIFP.proveedor_id == proveedor.id, EvidenciaIFP.fecha <= corte)
        .order_by(EvidenciaIFP.fecha, EvidenciaIFP.id)
    )
    evidencias = {r.dimension: r for r in registros}
    dimensiones, impedimentos = [], []
    evaluados = aportes = 0
    for dimension, peso in aplicables.items():
        ev = evidencias.get(dimension)
        valor, motivo = None, "Falta evidencia para esta dimensión."
        detalle = None
        if ev:
            detalle = dict(
                referencia=ev.referencia,
                origen=ev.origen,
                corte=ev.fecha.isoformat(),
                vigente_hasta=ev.vigente_hasta.isoformat(),
                datos=ev.valores,
            )
            if ev.vigente_hasta < corte:
                motivo = "La evidencia requiere actualización."
            else:
                valor, motivo = dato_puntaje(dimension, ev.valores, monto)
                if dimension == "sanciones" and ev.valores["vigente"]:
                    impedimentos.append(
                        {
                            "estado": "Posible impedimento",
                            "referencia": ev.referencia,
                            "accion": "Revisar alcance y vigencia con el órgano competente.",
                        }
                    )
        if valor is not None:
            evaluados += peso
            aportes += peso * valor
        dimensiones.append(
            dict(
                clave=dimension,
                nombre=ETIQUETAS[dimension],
                peso=peso,
                valor=valor,
                motivo=motivo,
                evidencia=detalle,
            )
        )
    cobertura = round(100 * evaluados / sum(aplicables.values()), 2)
    ifp = (
        round(100 * aportes / evaluados, 2)
        if evaluados and cobertura >= config()["cobertura_minima"]
        else None
    )
    confianza = (
        "Baja"
        if cobertura < 75
        else "Media"
        if cobertura < 90 or tipo == "natural"
        else "Alta"
    )
    nivel = (
        "No evaluado"
        if ifp is None
        else "Alta"
        if ifp >= 75
        else "Media"
        if ifp >= 50
        else "Baja"
    )
    return dict(
        id=proveedor.id,
        ruc=proveedor.ruc,
        razon_social=proveedor.razon_social,
        tipo=tipo,
        ifp=ifp,
        cobertura=cobertura,
        confianza=confianza,
        nivel=nivel,
        dimensiones=dimensiones,
        impedimentos=impedimentos,
        modelo=config()["version"],
        origen="simulado",
        categoria=categoria,
        corte=corte.isoformat(),
        monto=float(monto) if monto else None,
    )


def resumen_ifp(sesion, ruc, monto=None, categoria="servicios"):
    proveedor = sesion.scalar(select(Proveedor).where(Proveedor.ruc == ruc))
    if proveedor is None or not ruc.startswith("00"):
        return dict(ifp=None, cobertura=0, confianza="Baja", nivel="No evaluado")
    r = resultado_ifp(sesion, proveedor, monto, categoria)
    return {k: r[k] for k in ("ifp", "cobertura", "confianza", "nivel")}


def evaluar_vinculo(interviniente, vinculo, registros, corte=CORTE):
    if (
        not vinculo.verificado
        or vinculo.desde > corte
        or (vinculo.hasta and vinculo.hasta < corte)
    ):
        return []
    familiar = vinculo.parentesco in {
        "cónyuge",
        "conviviente",
        "progenitor de hijo",
    } or (
        vinculo.parentesco in {"consanguinidad", "afinidad"}
        and vinculo.grado is not None
        and 1 <= vinculo.grado <= config()["grado_parentesco"]
    )
    directo = vinculo.parentesco == "directo"
    participa = vinculo.cargo in {"socio", "accionista", "representante", "gerente"}
    senales = []
    if familiar and (participa or vinculo.cargo == "titular"):
        senales.append(
            (
                "R08",
                "Parentesco documentado de un interviniente con el titular o participante del proveedor.",
            )
        )
    if (directo or familiar) and participa:
        senales.append(
            (
                "R09",
                "Participación societaria o representación respaldada por el registro sintético.",
            )
        )
    acciones = {d.accion for d in registros}
    if (
        senales
        and interviniente.registro_completo
        and not acciones.intersection({"conflicto declarado", "abstención registrada"})
    ):
        senales.append(
            (
                "R11",
                "El registro interno revisado carece de declaración de este vínculo o abstención.",
            )
        )
    return [
        dict(
            regla=regla,
            motivo=motivo,
            evidencia=vinculo.evidencia,
            certeza="Alta",
            origen="simulado",
            base_legal="verificar",
            vinculo_id=vinculo.id,
            proceso=interviniente.proceso,
        )
        for regla, motivo in senales
    ]


def casos(s, proceso=None, ruc=None):
    consulta = (
        select(Vinculo, Interviniente, Proveedor)
        .join(Interviniente, Interviniente.id == Vinculo.interviniente_id)
        .join(Proveedor, Proveedor.id == Vinculo.proveedor_id)
    )
    if proceso:
        consulta = consulta.where(Interviniente.proceso == proceso)
    if ruc:
        consulta = consulta.where(Proveedor.ruc == ruc)
    resultado = []
    for v, actor, p in s.execute(consulta.order_by(Vinculo.id)):
        registros = list(
            s.scalars(
                select(Declaracion)
                .where(Declaracion.vinculo_id == v.id)
                .order_by(Declaracion.id.desc())
            )
        )
        senales = evaluar_vinculo(actor, v, registros)
        if not senales:
            continue
        historial = [
            dict(
                id=d.id,
                accion=d.accion,
                motivo=d.motivo,
                responsable=d.responsable,
                fecha=d.fecha.isoformat() + "Z",
            )
            for d in registros
        ]
        estado = registros[0].accion if registros else "Pendiente de revisión"
        resultado.append(
            dict(
                id=v.id,
                proceso=actor.proceso,
                servidor=actor.nombre,
                rol=actor.rol,
                familiar=v.persona,
                cargo=v.cargo,
                grado=v.grado,
                parentesco=v.parentesco,
                proveedor=p.razon_social,
                proveedor_id=p.id,
                ruc=p.ruc,
                senales=senales,
                evidencia=v.evidencia,
                desde=v.desde.isoformat(),
                estado=estado,
                historial=historial,
                registro_completo=actor.registro_completo,
            )
        )
    return resultado


def senales_proveedor(sesion, codigo_convocatoria, ruc):
    return [
        senal
        for caso in casos(sesion, codigo_convocatoria, ruc)
        for senal in caso["senales"]
    ]


def iniciar_integridad(motor):
    """Semilla aditiva sólo sobre identificadores demo conocidos. Nunca asocia datos adversos a RUC públicos."""
    with obtener_sesion(motor) as s:
        if motor.dialect.name == "sqlite":
            s.connection().exec_driver_sql("BEGIN IMMEDIATE")
        candidatos = list(
            s.scalars(
                select(Proveedor)
                .where(
                    Proveedor.ruc.startswith("00"),
                    Proveedor.razon_social.startswith("SIMULADO"),
                )
                .order_by(Proveedor.id)
                .limit(48)
            )
        )
        trio = list(
            s.scalars(
                select(Proveedor)
                .where(Proveedor.ruc.in_([AURORA, HORIZONTE, NOVA]))
                .order_by(Proveedor.ruc)
            )
        )
        naturales = []
        for numero in range(1, 10):
            ruc = f"008000000{numero:02d}"
            persona = s.scalar(select(Proveedor).where(Proveedor.ruc == ruc))
            if persona is None:
                persona = Proveedor(
                    ruc=ruc,
                    razon_social=f"Persona de prueba {numero:02d} (demo)",
                    domicilio="Campus de prueba (demo)",
                    representante="Titular (demo)",
                    fecha_constitucion=date(2018, 1, 1),
                )
                s.add(persona)
                s.flush()
            naturales.append(persona)
        for p in trio + candidatos + naturales:
            if s.get(Perfil, p.id):
                continue
            rng = random.Random(42 + int(p.ruc))
            natural = p in naturales
            s.add(Perfil(proveedor_id=p.id, tipo="natural" if natural else "jurídica"))
            adverso = p in candidatos and candidatos.index(p) % 13 == 4
            tension = p.ruc == HORIZONTE
            datos = {
                "registro": {"activo": True, "habido": True},
                "sanciones": {"vigente": adverso},
                "solvencia": {
                    "capacidad": 1100 if tension else rng.randint(28000, 85000)
                },
                "obligaciones": {"al_dia": not (tension or adverso)},
                "historial": {
                    "observados": 10,
                    "cumplidos": 6 if tension else 9 if adverso else 10,
                },
                "integridad": {"incumplimiento_confirmado": False},
            }
            if p.ruc == AURORA:
                datos["litigios"] = {"resolucion_firme_adversa": False}
            for k, medida in datos.items():
                if natural and k not in {"registro", "historial"}:
                    continue
                s.add(
                    EvidenciaIFP(
                        proveedor_id=p.id,
                        dimension=k,
                        valores=medida,
                        origen="simulado",
                        referencia=f"FIC-{p.ruc[-9:]}-{k}",
                        fecha=date(2026, 11, 1),
                        vigente_hasta=date(2027, 1, 31),
                        responsable="Generador sintético · semilla 42",
                    )
                )
        nova = next((p for p in trio if p.ruc == NOVA), None)
        if nova and not s.scalar(
            select(Interviniente).where(Interviniente.proceso == CAFETERIA)
        ):
            evaluador = Interviniente(
                proceso=CAFETERIA,
                codigo="EVA-03",
                nombre="Evaluadora Lumen (demo)",
                rol="Comité",
                registro_completo=True,
            )
            s.add(evaluador)
            s.flush()
            s.add(
                Vinculo(
                    interviniente_id=evaluador.id,
                    proveedor_id=nova.id,
                    persona="Socio Lumen (demo)",
                    parentesco="consanguinidad",
                    grado=2,
                    cargo="socio",
                    verificado=True,
                    evidencia="ACTA-DEMO-03 · filiación de hermanos y participación societaria",
                    desde=date(2026, 1, 1),
                )
            )
        if trio:
            sembrar_concesiones(s, trio)
