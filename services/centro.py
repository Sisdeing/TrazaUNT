"""Centro de alertas y fichas históricas por empresa (v5.1).

Reúne en una sola vista las señales que ya produce TrazaUNT, sin crear datos nuevos:

* reglas R01–R06 sobre las contrataciones (tabla ``alertas``),
* coincidencias persona–empresa CI01–CI06 en las convocatorias (tabla ``coincidencias``),
* alertas TZ de los expedientes de trazabilidad (tabla ``tz_alertas``).

Cada señal se clasifica en una de cinco categorías (posible fraccionamiento, posible
colusión, posible conflicto de intereses, concentración de contrataciones y otras señales
de control). Ninguna es una conclusión: son indicios para revisión humana.

Las fichas por empresa se construyen con las contrataciones, postulaciones, admisiones,
coincidencias y alertas que ya existen para cada proveedor. Si un dato no existe, se
informa como «no disponible».
"""
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
import re
from zoneinfo import ZoneInfo

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from db.coincidencias import Admision, Coincidencia, RevisionCoincidencia, SeguimientoAlerta
from db.convocatorias import Convocatoria, Postulacion
from db.database import obtener_sesion
from db.models import Alerta, Bitacora, Contratacion, Entidad, Pago, Proveedor
from db.trazabilidad import AlertaTZ, Evento, Expediente, Fase
from services.alertas_service import revisar as revisar_regla
from services.coincidencias import Decision as DecisionCI, revisar as revisar_coincidencia
from services.integridad import resultado_ifp
from services.trazabilidad import Accion as AccionTZ, revisar_alerta as revisar_tz

LIMA = ZoneInfo("America/Lima")
router = APIRouter(prefix="/api", tags=["Centro de alertas y empresas"])

CATEGORIAS = {
    "fraccionamiento": (
        "Posible fraccionamiento",
        "Contrataciones parecidas, cercanas en el tiempo y con el mismo proveedor que, sumadas, "
        "superan el umbral de referencia; o montos ubicados justo por debajo de ese umbral.",
    ),
    "colusion": (
        "Posible colusión",
        "Empresas que compiten en un mismo proceso pero comparten domicilio o representante: "
        "podrían no actuar de forma independiente.",
    ),
    "conflicto": (
        "Posible conflicto de intereses",
        "Coincidencias o vínculos documentados entre personas de la universidad (comité, área "
        "usuaria) y empresas postulantes o sus representantes.",
    ),
    "concentracion": (
        "Concentración de contrataciones",
        "Un proveedor concentra una proporción elevada de los contratos de una entidad en el año.",
    ),
    "control": (
        "Otras señales de control",
        "Pagos sin sustento completo, fechas incoherentes, proveedor reciente con monto alto y "
        "controles de las fases de los expedientes.",
    ),
}
REGLAS = {
    "R01_FRACCIONAMIENTO": ("fraccionamiento", "Posible fraccionamiento de una misma necesidad"),
    "R04_MONTO_CERCANO_UMBRAL": ("fraccionamiento", "Monto justo por debajo del umbral de referencia"),
    "R02_PROVEEDOR_DOMINANTE": ("concentracion", "Proveedor que concentra los contratos de una entidad"),
    "R03_PAGOS_SIN_SUSTENTO": ("control", "Pago con sustento documental incompleto"),
    "R05_FECHAS_INCOHERENTES": ("control", "Fechas incoherentes en el expediente"),
    "R06_PROVEEDOR_RECIENTE": ("control", "Proveedor de reciente creación con contrato de monto alto"),
}
CI_CATEGORIA = {"CI01": "conflicto", "CI02": "conflicto", "CI03": "conflicto", "CI06": "conflicto",
                "CI04": "colusion", "CI05": "colusion"}
TZ = {
    "TZ01": ("media", "Se avanzó sin cerrar la fase anterior"),
    "TZ02": ("media", "Requisito obligatorio sin verificar"),
    "TZ04": ("alta", "Pago sin conformidad completa"),
    "TZ05": ("media", "Observación pendiente en una fase que ya avanzó"),
    "TZ06": ("alta", "Una misma cuenta en funciones que deben estar separadas"),
    "TZ08": ("baja", "Plazo de la fase vencido"),
    "TZ09": ("alta", "Monto pagado inconsistente"),
    "TZ11": ("media", "Avance sin verificación previa"),
    "TZ13": ("alta", "Documento modificado: su huella ya no coincide"),
    "TZ14": ("baja", "Fase reabierta más de una vez"),
}
TZ_REVISAR = {
    "TZ01": "Verificar por qué se inició una fase sin cerrar la anterior y si faltó algún control.",
    "TZ02": "Revisar si el requisito obligatorio se presentó y verificó antes de avanzar.",
    "TZ04": "Confirmar que exista la conformidad cerrada y sin observaciones antes del pago.",
    "TZ05": "Revisar la observación abierta y si la fase debió avanzar sin resolverla.",
    "TZ06": "Confirmar si una misma persona pidió, aprobó o pagó; la segregación de funciones evita conflictos.",
    "TZ08": "Revisar el motivo del retraso y reprogramar o justificar el plazo.",
    "TZ09": "Contrastar lo pagado con lo autorizado y con el monto del contrato.",
    "TZ11": "Verificar que la revisión del documento se haya hecho antes del visto bueno o el cierre.",
    "TZ13": "Comparar el archivo actual con la versión registrada: su contenido cambió.",
    "TZ14": "Revisar por qué la fase se reabrió varias veces y qué se corrigió.",
}
ESTADOS = {"pendiente": "Pendiente de revisión", "en_revision": "En revisión",
           "revisada": "Revisada", "descartada": "Descartada"}
PRIORIDAD = {"alta": 0, "media": 1, "baja": 2}


def _iso(valor):
    """Fecha y hora en Lima, en ISO; acepta datetime ingenuo (UTC), date o texto ISO."""
    if valor is None:
        return None
    if isinstance(valor, str):
        try:
            valor = datetime.fromisoformat(valor)
        except ValueError:
            return valor
    if isinstance(valor, datetime):
        if valor.tzinfo is None:
            valor = valor.replace(tzinfo=timezone.utc)
        return valor.astimezone(LIMA).isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    return str(valor)


def _soles(v):
    try:
        return f"S/ {float(v):,.2f}"
    except (TypeError, ValueError):
        return "No disponible"


def _llano(texto):
    """Quita detalles internos (IDs, «tokens canónicos») para que el texto se lea sin jerga."""
    texto = re.sub(r" \[(ID|contratación) \d+\]", "", texto)
    texto = re.sub(r"(y )?la agrupación por tokens canónicos «[^»]*»", "con objeto similar", texto)
    texto = texto.replace("ventana inclusiva", "periodo").replace("días inclusivos", "días")
    return texto


def _partes(explicacion):
    """Extrae «Qué se observó», «Criterio aplicado» y «Qué revisar» del texto de la regla."""
    bloque = _llano((explicacion or "").split("\n\n")[-1])
    out = {}
    for linea in bloque.splitlines():
        for clave, prefijo in (("observado", "Qué se observó:"), ("criterio", "Criterio aplicado:"),
                               ("revisar", "Qué revisar:")):
            if linea.startswith(prefijo):
                out[clave] = linea[len(prefijo):].strip()
    return out


def _comentario(b):
    """Los registros automáticos guardan datos técnicos: se muestran con una frase legible."""
    fijos = {"detectada": "La regla se activó; requiere revisión humana.",
             "reevaluada": "El sistema volvió a evaluar la alerta con los datos actualizados.",
             "no_vigente": "La regla ya no se activa; se conserva el historial."}
    if b.accion in fijos or str(b.comentario).lstrip().startswith(("{", "[")):
        return fijos.get(b.accion, "Registro automático del sistema.")
    return b.comentario


def _empresa(p):
    return dict(id=p.id, ruc=p.ruc, nombre=p.razon_social) if p else None


def _estado(origen_estado, mapa, marcado):
    e = mapa.get(origen_estado, "pendiente")
    if e == "pendiente" and marcado:
        e = "en_revision"
    return e


# ------------------------------------------------------------------ construcción
def _clave_grupo(a):
    """Las reglas R01 y R02 marcan cada contrato del patrón; en el centro se ven como un solo caso."""
    ev = a.evidencia_json
    if a.regla_id.startswith("R01") and ev.get("contratos"):
        return ("R01", tuple(sorted(x["id"] for x in ev["contratos"])))
    if a.regla_id.startswith("R02"):
        return ("R02", ev.get("entidad_id"), ev.get("proveedor_id"), ev.get("anio"))
    return ("X", a.id)


def _reglas(s, marcas):
    q = (select(Alerta, Contratacion, Proveedor, Entidad)
         .join(Contratacion, Contratacion.id == Alerta.contratacion_id)
         .join(Proveedor, Proveedor.id == Contratacion.proveedor_id)
         .join(Entidad, Entidad.id == Contratacion.entidad_id)
         .order_by(Alerta.id))
    grupos = defaultdict(list)
    for f in s.execute(q):
        if f[0].evidencia_json.get("_vigente", True):
            grupos[_clave_grupo(f[0])].append(f)
    detectadas = dict(s.execute(select(Bitacora.alerta_id, func.min(Bitacora.fecha))
                                .where(Bitacora.accion == "detectada").group_by(Bitacora.alerta_id)).all())
    out = []
    for filas in grupos.values():
        a, c, p, en = filas[0]
        categoria, titulo = REGLAS.get(a.regla_id, ("control", a.regla_id.replace("_", " ").capitalize()))
        uid = f"R-{a.id}"
        estados = {x[0].estado for x in filas}
        estado = "pendiente" if "pendiente" in estados else ("descartada" if estados == {"descartada"} else "confirmada")
        contratos = sorted({x[1].id: x[1] for x in filas}.values(), key=lambda x: (x.fecha, x.id))
        proceso = dict(tipo="Contratación", id=c.id, codigo=c.codigo, nombre=c.objeto, entidad=en.nombre,
                       enlace=f"#expedientes/{c.id}")
        if len(contratos) > 1:
            proceso.update(id=contratos[0].id, codigo=f"{contratos[0].codigo} y {len(contratos) - 1} más",
                           nombre=f"{len(contratos)} contratos con {en.nombre}", enlace=f"#expedientes/{contratos[0].id}")
        fechas = [detectadas.get(x[0].id) for x in filas if detectadas.get(x[0].id)]
        out.append(dict(
            uid=uid, origen="regla", origen_id=a.id, ids=[x[0].id for x in filas], contratos_ids=[x.id for x in contratos],
            codigo=a.regla_id.split("_")[0], categoria=categoria, titulo=titulo, prioridad=a.severidad,
            estado=_estado(estado, {"pendiente": "pendiente", "confirmada": "revisada", "descartada": "descartada"}, uid in marcas),
            estado_origen=estado, fecha_deteccion=_iso(min(fechas)) if fechas else None,
            fecha_hecho=contratos[0].fecha.isoformat(), empresas=[_empresa(p)], proceso=proceso,
            descripcion=_partes(a.explicacion).get("observado") or titulo, puntaje=max(float(x[0].score) for x in filas)))
    return out


def _coincidencias(s, marcas):
    filas = s.execute(select(Coincidencia, Convocatoria).join(Convocatoria, Convocatoria.id == Coincidencia.referencia_id)
                      .where(Coincidencia.vigente.is_(True))).all()
    rucs = {}
    for x, _ in filas:
        for lado in (x.sujeto_a, x.sujeto_b):
            for r in (lado.get("ruc"), (lado.get("empresa") or {}).get("ruc")):
                if r:
                    rucs[r] = None
    if rucs:
        for p in s.scalars(select(Proveedor).where(Proveedor.ruc.in_(list(rucs)))):
            rucs[p.ruc] = p
    out = []
    for x, conv in filas:
        uid = f"CI-{x.id}"
        empresas, vistos = [], set()
        for lado in (x.sujeto_a, x.sujeto_b):
            for r in (lado.get("ruc"), (lado.get("empresa") or {}).get("ruc")):
                if r and r not in vistos:
                    vistos.add(r)
                    p = rucs.get(r)
                    nombre = p.razon_social if p else (lado.get("empresa") or lado).get("nombre")
                    empresas.append(dict(id=p.id if p else None, ruc=r, nombre=nombre))
        out.append(dict(
            uid=uid, origen="coincidencia", origen_id=x.id, codigo=x.tipo, categoria=CI_CATEGORIA.get(x.tipo, "conflicto"),
            titulo=x.titulo, prioridad=x.nivel,
            estado=_estado(x.estado, {"pendiente": "pendiente", "derivada": "revisada", "aclarada": "descartada"}, uid in marcas),
            estado_origen=x.estado, fecha_deteccion=_iso(x.detectada), fecha_hecho=conv.apertura.isoformat(),
            empresas=empresas, proceso=dict(tipo="Convocatoria", id=conv.id, codigo=conv.codigo, nombre=conv.nombre,
                                             entidad="Universidad Nacional de Trujillo", enlace=f"#convocatorias/{conv.id}"),
            descripcion=x.detalle, puntaje=None))
    return out


def _tz(s, marcas):
    filas = s.execute(select(AlertaTZ, Expediente).join(Expediente, Expediente.id == AlertaTZ.expediente_id)
                      .where(AlertaTZ.vigente.is_(True))).all()
    out = []
    for a, e in filas:
        prioridad, titulo = TZ.get(a.regla, ("media", a.regla))
        uid = f"TZ-{a.id}"
        out.append(dict(
            uid=uid, origen="trazabilidad", origen_id=a.id, codigo=a.regla, categoria="control", titulo=titulo,
            prioridad=prioridad,
            estado=_estado(a.estado, {"pendiente": "pendiente", "revisada": "revisada", "descartada": "descartada"}, uid in marcas),
            estado_origen=a.estado, fecha_deteccion=_iso(a.fecha), fecha_hecho=(a.fecha or "")[:10] or None,
            empresas=[], proceso=dict(tipo="Expediente", id=e.id, codigo=e.codigo, nombre=e.nombre, entidad=e.area,
                                      enlace=f"#trazabilidad/{e.id}"),
            descripcion=a.descripcion, puntaje=None))
    return out


def todas(s):
    marcas = {m.uid for m in s.scalars(select(SeguimientoAlerta))}
    items = _reglas(s, marcas) + _coincidencias(s, marcas) + _tz(s, marcas)
    orden = list(CATEGORIAS)
    items.sort(key=lambda x: (x["estado"] in ("revisada", "descartada"), PRIORIDAD.get(x["prioridad"], 3),
                              orden.index(x["categoria"]), -(x["puntaje"] or 0), x["uid"]))
    for x in items:
        x["categoria_texto"] = CATEGORIAS[x["categoria"]][0]
        x["estado_texto"] = ESTADOS[x["estado"]]
    return items


def _evidencia_regla(s, a, c):
    ev = {k: v for k, v in a.evidencia_json.items() if not k.startswith("_")}
    r = a.regla_id
    indicadores, registros = [], []
    codigos = lambda ids: {x.id: x for x in s.scalars(select(Contratacion).where(Contratacion.id.in_(ids)))}
    if r.startswith("R01"):
        indicadores = [("Contratos agrupados", ev.get("cantidad_contratos")),
                       ("Monto acumulado", _soles(ev.get("monto_acumulado"))),
                       ("Periodo observado", f"{ev.get('fecha_inicio')} a {ev.get('ultima_fecha_observada')}"),
                       ("Umbral de referencia", _soles(ev.get("parametros_aplicados", {}).get("umbral_monto"))),
                       ("Objeto", ", ".join(ev.get("objetos_originales", [])) or "No disponible")]
        registros = [dict(tipo="Contrato", codigo=x["codigo"], fecha=x["fecha"], monto=_soles(x["monto"]),
                          detalle=x["objeto"], enlace=f"#expedientes/{x['id']}") for x in ev.get("contratos", [])]
    elif r.startswith("R02"):
        ent = s.get(Entidad, ev.get("entidad_id"))
        indicadores = [("Participación del proveedor", f"{round(100 * float(ev.get('proporcion_observada', 0)))} %"),
                       ("Contratos del proveedor", f"{ev.get('cantidad_proveedor')} de {ev.get('cantidad_entidad')}"),
                       ("Entidad", ent.nombre if ent else "No disponible"), ("Año", ev.get("anio")),
                       ("Proporción mínima configurada", f"{round(100 * ev.get('parametros_aplicados', {}).get('proporcion_minima', 0))} %")]
        mapa = codigos(ev.get("contrataciones_proveedor", []))
        registros = [dict(tipo="Contrato", codigo=x.codigo, fecha=x.fecha.isoformat(), monto=_soles(x.monto),
                          detalle=x.objeto, enlace=f"#expedientes/{x.id}") for x in sorted(mapa.values(), key=lambda x: x.fecha)]
    elif r.startswith("R03"):
        indicadores = [("Pagos afectados", ev.get("cantidad_pagos_afectados"))]
        registros = [dict(tipo="Pago", codigo=f"Pago {x['pago_id']}", fecha=x["fecha_pago"], monto=_soles(x["monto"]),
                          detalle="Falta: " + ", ".join(x.get("documentos_faltantes", [])), enlace=f"#expedientes/{c.id}")
                     for x in ev.get("pagos_sin_sustento", [])]
    elif r.startswith("R04"):
        indicadores = [("Monto del contrato", _soles(ev.get("monto"))), ("Umbral de referencia", _soles(ev.get("umbral_monto"))),
                       ("Distancia al umbral", _soles(ev.get("distancia_al_umbral")))]
    elif r.startswith("R05"):
        for x in ev.get("inconsistencias", []):
            indicadores += [("Inconsistencia", str(x.get("tipo", "")).replace("_", " ")),
                            ("Fecha del contrato", x.get("fecha_contrato")), ("Fecha del pago", x.get("fecha_pago")),
                            ("Días de diferencia", x.get("dias_anticipacion"))]
    elif r.startswith("R06"):
        indicadores = [("Constitución del proveedor", ev.get("fecha_constitucion")), ("Fecha del contrato", ev.get("fecha_contrato")),
                       ("Antigüedad al contratar", f"{ev.get('antiguedad_dias')} días"), ("Monto", _soles(ev.get("monto")))]
    if not registros:
        registros = [dict(tipo="Contrato", codigo=c.codigo, fecha=c.fecha.isoformat(), monto=_soles(c.monto),
                          detalle=c.objeto, enlace=f"#expedientes/{c.id}")]
    return [dict(nombre=k, valor=str(v) if v is not None else "No disponible") for k, v in indicadores], registros


def detalle(s, uid):
    base = next((x for x in todas(s) if x["uid"] == uid), None)
    if base is None:
        raise HTTPException(404, "La alerta no existe o ya no está vigente.")
    seg = s.get(SeguimientoAlerta, uid)
    historial, indicadores, registros, explicacion = [], [], [], {}
    if base["origen"] == "regla":
        a = s.get(Alerta, base["origen_id"])
        c = s.get(Contratacion, a.contratacion_id)
        indicadores, registros = _evidencia_regla(s, a, c)
        explicacion = _partes(a.explicacion)
        vistos = set()
        for b in s.scalars(select(Bitacora).where(Bitacora.alerta_id.in_(base["ids"])).order_by(Bitacora.id)):
            # En un patrón agrupado cada contrato registra la misma detección: se muestra una vez.
            clave = (b.accion, b.analista, b.comentario if b.accion not in ("detectada", "reevaluada") else "")
            if clave in vistos:
                continue
            vistos.add(clave)
            historial.append(dict(fecha=_iso(b.fecha), accion={"detectada": "Detectada", "reevaluada": "Reevaluada",
                                                               "confirmada": "Revisada (confirmada)", "descartada": "Descartada",
                                                               "no_vigente": "Ya no aplica"}.get(b.accion, b.accion),
                                  autor=b.analista, texto=_comentario(b)))
    elif base["origen"] == "coincidencia":
        x = s.get(Coincidencia, base["origen_id"])
        e = x.evidencia or {}
        indicadores = [dict(nombre=k, valor=str(v)) for k, v in (
            ("Dato comparado", e.get("campo")), ("Persona o empresa A", x.sujeto_a.get("nombre")),
            ("Rol A", x.sujeto_a.get("rol")), ("Persona o empresa B", x.sujeto_b.get("nombre")),
            ("Rol B", x.sujeto_b.get("rol")), ("Valor A", e.get("valor_a")), ("Valor B", e.get("valor_b")),
            ("Términos en común", ", ".join(e.get("terminos", [])) or None),
            ("Referencia documental", e.get("referencia")), ("Declaración registrada", e.get("declaracion"))) if v]
        registros = [dict(tipo="Fuente", codigo=lado.get("fuente", "No disponible"), fecha=None, monto=None,
                          detalle=f"{lado.get('nombre')} · {lado.get('rol')}", enlace=base["proceso"]["enlace"])
                     for lado in (x.sujeto_a, x.sujeto_b)]
        explicacion = dict(observado=x.detalle, criterio=e.get("criterio"),
                           revisar="Verificar la identidad de las personas y la independencia de las empresas con "
                                   "documentos (DNI, declaraciones juradas, registro de vínculos) antes de concluir.")
        historial = [dict(fecha=_iso(x.detectada), accion="Detectada", autor="Sistema", texto="Coincidencia detectada automáticamente.")]
        historial += [dict(fecha=_iso(r.fecha), accion={"aclarada": "Descartada (aclarada sin incidencia)",
                                                        "derivada": "Revisada (derivada a integridad)"}.get(r.decision, r.decision),
                           autor=r.autor, texto=r.justificacion)
                      for r in s.scalars(select(RevisionCoincidencia).where(RevisionCoincidencia.coincidencia_id == x.id)
                                         .order_by(RevisionCoincidencia.id))]
    else:
        a = s.get(AlertaTZ, base["origen_id"])
        fases = {f.id: f for f in s.scalars(select(Fase).where(Fase.expediente_id == a.expediente_id))}
        origen = fases.get((a.evidencia or {}).get("origen_fase_id"))
        indicadores = [dict(nombre="Fase donde se detectó", valor=fases[a.fase_id].nombre if a.fase_id in fases else "No disponible"),
                       dict(nombre="Posible origen", valor=origen.nombre if origen else "No disponible")]
        eventos = s.scalars(select(Evento).where(Evento.expediente_id == a.expediente_id,
                                                 Evento.fase_id.in_([a.fase_id] + ([origen.id] if origen else []))).order_by(Evento.id))
        nombres = {"iniciar": "Fase iniciada", "cargar_documento": "Documento subido", "verificar": "Documento verificado",
                   "observar": "Observación registrada", "subsanar": "Subsanación presentada", "cerrar_observacion": "Subsanación verificada",
                   "visto_bueno": "Visto bueno", "pago": "Pago registrado", "cerrar": "Fase cerrada", "reabrir": "Fase reabierta"}
        registros = [dict(tipo="Actuación", codigo=nombres.get(v.accion, v.accion.replace("_", " ")), fecha=(v.fecha or "")[:10],
                          monto=None, detalle=f"{v.responsable} · {fases[v.fase_id].nombre if v.fase_id in fases else ''}",
                          enlace=base["proceso"]["enlace"]) for v in eventos if v.accion in nombres]
        explicacion = dict(observado=a.descripcion, criterio="Regla de control de la trazabilidad " + a.regla + ".",
                           revisar=TZ_REVISAR.get(a.regla, "Revisar las actuaciones de la fase."))
        historial = [dict(fecha=_iso(a.fecha), accion="Detectada", autor="Sistema", texto=a.descripcion)]
        historial += [dict(fecha=_iso(v.fecha), accion="Revisada" if v.datos.get("decision") == "revisada" else "Descartada",
                           autor=v.responsable, texto=v.datos.get("justificacion", ""))
                      for v in s.scalars(select(Evento).where(Evento.expediente_id == a.expediente_id,
                                                              Evento.accion == "revision_alerta").order_by(Evento.id))
                      if v.datos.get("alerta_id") == a.id]
    if seg:
        historial.append(dict(fecha=_iso(seg.fecha), accion="Tomada para revisión", autor=seg.responsable,
                              texto="La alerta pasó a «En revisión»."))
        historial.sort(key=lambda h: h["fecha"] or "")
    return dict(base, indicadores=indicadores, registros=registros, explicacion=explicacion, historial=historial,
                categoria_ayuda=CATEGORIAS[base["categoria"]][1],
                aviso="Indicio para revisión humana. No constituye una prueba ni una acusación.")


def _usuario(request, escritura=False):
    u = getattr(request.state, "usuario", None)
    if not u:
        raise HTTPException(401, "Inicia sesión para continuar.")
    if u["rol"] not in ("analista", "administrador"):
        raise HTTPException(403, "El centro de alertas es para el equipo de la universidad.")
    return u


# ------------------------------------------------------------------ rutas: alertas
@router.get("/centro-alertas")
def listar(request: Request, categoria: str = Query("", max_length=20), prioridad: str = Query("", max_length=10),
           estado: str = Query("", max_length=20), desde: str = Query("", max_length=10), hasta: str = Query("", max_length=10),
           q: str = Query("", max_length=120), empresa: int | None = Query(None, gt=0),
           pagina: int = Query(1, ge=1), tamano: int = Query(20, ge=1, le=100)):
    _usuario(request)
    with obtener_sesion(request.app.state.motor) as s:
        items = todas(s)
    resumen = dict(total=len(items),
                   abiertas=sum(x["estado"] in ("pendiente", "en_revision") for x in items),
                   por_categoria={k: dict(nombre=v[0], ayuda=v[1],
                                          abiertas=sum(x["categoria"] == k and x["estado"] in ("pendiente", "en_revision") for x in items),
                                          total=sum(x["categoria"] == k for x in items)) for k, v in CATEGORIAS.items()},
                   por_prioridad=dict(Counter(x["prioridad"] for x in items if x["estado"] in ("pendiente", "en_revision"))),
                   por_estado=dict(Counter(x["estado"] for x in items)))
    t = q.strip().lower()
    filtrados = [x for x in items
                 if (not categoria or x["categoria"] == categoria) and (not prioridad or x["prioridad"] == prioridad)
                 and (not estado or x["estado"] == estado or (estado == "abiertas" and x["estado"] in ("pendiente", "en_revision")))
                 and (not desde or (x["fecha_hecho"] or "") >= desde) and (not hasta or (x["fecha_hecho"] or "") <= hasta)
                 and (not empresa or any(e and e.get("id") == empresa for e in x["empresas"]))
                 and (not t or t in " ".join([x["titulo"], x["codigo"], x["proceso"]["codigo"], x["proceso"]["nombre"],
                                              *[(e or {}).get("nombre") or "" for e in x["empresas"]],
                                              *[(e or {}).get("ruc") or "" for e in x["empresas"]]]).lower())]
    inicio = (pagina - 1) * tamano
    return dict(items=filtrados[inicio:inicio + tamano], total=len(filtrados), pagina=pagina, tamano=tamano, resumen=resumen,
                categorias={k: dict(nombre=v[0], ayuda=v[1]) for k, v in CATEGORIAS.items()})


@router.get("/centro-alertas/{uid}")
def ver(uid: str, request: Request):
    _usuario(request)
    with obtener_sesion(request.app.state.motor) as s:
        return detalle(s, uid)


@router.post("/centro-alertas/{uid}/tomar")
def tomar(uid: str, request: Request):
    u = _usuario(request, True)
    with obtener_sesion(request.app.state.motor) as s:
        s.connection().exec_driver_sql("BEGIN IMMEDIATE")
        actual = detalle(s, uid)
        if actual["estado"] != "pendiente":
            raise HTTPException(409, "Solo se puede tomar una alerta pendiente de revisión.")
        s.add(SeguimientoAlerta(uid=uid, responsable=u.get("nombre") or u["usuario"], cuenta=u["usuario"]))
        s.flush()
        return detalle(s, uid)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    decision: Literal["revisada", "descartada"]
    justificacion: str = Field(min_length=15, max_length=2000)


@router.post("/centro-alertas/{uid}/decision")
def decidir(uid: str, datos: Decision, request: Request):
    """Registra la decisión en el origen de la alerta, con su propia bitácora e historial."""
    u = _usuario(request, True)
    with obtener_sesion(request.app.state.motor) as s:
        actual = detalle(s, uid)
    if actual["estado"] in ("revisada", "descartada"):
        raise HTTPException(409, "La alerta ya tiene una decisión registrada.")
    if actual["origen"] == "regla":
        destino = "confirmada" if datos.decision == "revisada" else "descartada"
        with obtener_sesion(request.app.state.motor) as s:
            pendientes = [(a.id, a.estado) for a in s.scalars(select(Alerta).where(Alerta.id.in_(actual["ids"])))
                          if a.estado != destino]
        try:
            for aid, estado in pendientes:
                revisar_regla(request.app.state.motor, aid, destino, u.get("nombre") or u["usuario"], datos.justificacion, estado)
        except ValueError as e:
            raise HTTPException(409, str(e)) from e
    elif actual["origen"] == "coincidencia":
        revisar_coincidencia(actual["origen_id"], DecisionCI(decision="derivada" if datos.decision == "revisada" else "aclarada",
                                                             justificacion=datos.justificacion), request)
    else:
        revisar_tz(actual["proceso"]["id"], actual["origen_id"],
                   AccionTZ(accion=datos.decision, revision=0, justificacion=datos.justificacion), request)
    with obtener_sesion(request.app.state.motor) as s:
        return detalle(s, uid)


# ------------------------------------------------------------------ rutas: empresas
@router.get("/fichas-empresa")
def empresas(request: Request, q: str = Query("", max_length=120), orden: str = Query("alertas", pattern="^(alertas|contratos|monto|nombre)$"),
             pagina: int = Query(1, ge=1), tamano: int = Query(20, ge=1, le=100)):
    _usuario(request)
    with obtener_sesion(request.app.state.motor) as s:
        agregados = {pid: (n, float(m or 0), ult, ne) for pid, n, m, ult, ne in s.execute(
            select(Contratacion.proveedor_id, func.count(), func.sum(Contratacion.monto), func.max(Contratacion.fecha),
                   func.count(func.distinct(Contratacion.entidad_id))).group_by(Contratacion.proveedor_id))}
        postulaciones = dict(s.execute(select(Postulacion.proveedor_id, func.count()).group_by(Postulacion.proveedor_id)).all())
        alertas = Counter()
        for x in todas(s):
            if x["estado"] in ("pendiente", "en_revision"):
                for e in x["empresas"]:
                    if e and e.get("id"):
                        alertas[e["id"]] += 1
        items = []
        t = q.strip().lower()
        for p in s.scalars(select(Proveedor)):
            if t and t not in (p.ruc + " " + p.razon_social).lower():
                continue
            n, monto, ult, ne = agregados.get(p.id, (0, 0.0, None, 0))
            items.append(dict(id=p.id, ruc=p.ruc, nombre=p.razon_social, contratos=n, monto=monto,
                              ultima=ult.isoformat() if ult else None, entidades=ne,
                              postulaciones=postulaciones.get(p.id, 0), alertas=alertas.get(p.id, 0)))
    clave = {"alertas": lambda x: (-x["alertas"], -x["contratos"], x["nombre"]),
             "contratos": lambda x: (-x["contratos"], x["nombre"]), "monto": lambda x: (-x["monto"], x["nombre"]),
             "nombre": lambda x: x["nombre"]}[orden]
    items.sort(key=clave)
    inicio = (pagina - 1) * tamano
    return dict(items=items[inicio:inicio + tamano], total=len(items), pagina=pagina, tamano=tamano)


@router.get("/fichas-empresa/{pid}")
def ficha_empresa(pid: int, request: Request):
    _usuario(request)
    with obtener_sesion(request.app.state.motor) as s:
        p = s.get(Proveedor, pid)
        if p is None:
            raise HTTPException(404, "La empresa no está registrada.")
        entidades = {e.id: e.nombre for e in s.scalars(select(Entidad))}
        contratos = list(s.scalars(select(Contratacion).where(Contratacion.proveedor_id == pid).order_by(Contratacion.fecha)))
        alertas = [x for x in todas(s) if any(e and e.get("id") == pid for e in x["empresas"])]
        por_contrato = defaultdict(list)
        for a in alertas:
            for cid in a.get("contratos_ids", []):
                por_contrato[cid].append(a["codigo"])
        pagos_faltan = {c for c, in s.execute(select(Pago.contratacion_id).where(
            Pago.contratacion_id.in_([c.id for c in contratos]),
            (Pago.tiene_conformidad.is_(False)) | (Pago.tiene_comprobante.is_(False))))}
        lista = [dict(id=c.id, codigo=c.codigo, fecha=c.fecha.isoformat(), entidad=entidades.get(c.entidad_id, "No disponible"),
                      objeto=c.objeto, monto=float(c.monto), tipo=c.tipo_proceso, postores=c.n_postores,
                      alertas=por_contrato.get(c.id, []), pago_incompleto=c.id in pagos_faltan, enlace=f"#expedientes/{c.id}")
                 for c in contratos]
        posts = s.execute(select(Postulacion, Convocatoria).join(Convocatoria, Convocatoria.id == Postulacion.convocatoria_id)
                          .where(Postulacion.proveedor_id == pid).order_by(Postulacion.fecha)).all()
        admisiones = defaultdict(list)
        for a in s.scalars(select(Admision).where(Admision.postulacion_id.in_([x.id for x, _ in posts])).order_by(Admision.id)):
            admisiones[a.postulacion_id].append(a)
        postulaciones = []
        for x, c in posts:
            ult = admisiones[x.id][-1] if admisiones[x.id] else None
            ganador = (c.resultado or {}).get("postulante_id") == x.id if isinstance(c.resultado, dict) else False
            postulaciones.append(dict(convocatoria=c.codigo, nombre=c.nombre, fecha=_iso(x.fecha), oferta=float(x.oferta),
                                      estado_convocatoria=c.estado, admision=ult.estado if ult else "pendiente",
                                      motivo=ult.motivo if ult else None, adjudicada=ganador, enlace=f"#convocatorias/{c.id}"))
        meses = defaultdict(lambda: dict(monto=0.0, contratos=0, alertas=0))
        for c in contratos:
            m = meses[c.fecha.strftime("%Y-%m")]
            m["monto"] += float(c.monto)
            m["contratos"] += 1
        for a in alertas:
            if a["fecha_hecho"]:
                meses[a["fecha_hecho"][:7]]["alertas"] += 1
        eventos = [dict(fecha=p.fecha_constitucion.isoformat(), tipo="empresa", titulo="Constitución de la empresa",
                        detalle="Fecha registrada en el padrón del sistema.")]
        eventos += [dict(fecha=c["fecha"], tipo="contrato", titulo=f"Contrato {c['codigo']}",
                         detalle=f"{c['objeto']} · {c['entidad']} · S/ {c['monto']:,.2f}", enlace=c["enlace"]) for c in lista]
        eventos += [dict(fecha=x["fecha"][:10], tipo="postulacion", titulo=f"Postuló a {x['convocatoria']}",
                         detalle=f"{x['nombre']} · oferta S/ {x['oferta']:,.2f}", enlace=x["enlace"]) for x in postulaciones]
        eventos += [dict(fecha=a["fecha_hecho"], tipo="alerta-" + a["prioridad"], titulo=a["titulo"],
                         detalle=f"{a['categoria_texto']} · {a['estado_texto']} · {a['proceso']['codigo']}", uid=a["uid"])
                    for a in alertas if a["fecha_hecho"]]
        eventos.sort(key=lambda e: e["fecha"] or "", reverse=True)
        try:
            ifp = resultado_ifp(s, p) if p.ruc.startswith("00") else None
        except Exception:  # el IFP es complementario: su ausencia no impide mostrar la ficha
            ifp = None
        monto_total = sum(c["monto"] for c in lista)
        return dict(
            empresa=dict(id=p.id, ruc=p.ruc, nombre=p.razon_social, representante=p.representante, domicilio=p.domicilio,
                         constitucion=p.fecha_constitucion.isoformat(), origen="Registro sintético de demostración"
                         if p.ruc.startswith("00") else "Registro del sistema"),
            resumen=dict(participaciones=len(lista) + len(postulaciones), contratos=len(lista),
                         postulaciones=len(postulaciones), entidades=len({c["entidad"] for c in lista}),
                         monto_total=monto_total, primera=lista[0]["fecha"] if lista else None,
                         ultima=lista[-1]["fecha"] if lista else None,
                         alertas=len(alertas), alertas_abiertas=sum(a["estado"] in ("pendiente", "en_revision") for a in alertas)),
            entidades=[dict(nombre=k, contratos=v, monto=sum(c["monto"] for c in lista if c["entidad"] == k))
                       for k, v in Counter(c["entidad"] for c in lista).most_common()],
            contratos=lista, postulaciones=postulaciones,
            meses=[dict(mes=k, **v) for k, v in sorted(meses.items())],
            alertas=alertas,
            alertas_por_categoria={k: sum(a["categoria"] == k for a in alertas) for k in CATEGORIAS},
            categorias={k: v[0] for k, v in CATEGORIAS.items()},
            linea_tiempo=eventos, ifp=ifp,
            limitaciones=["Los contratos registrados son adjudicaciones: el sistema no guarda los procesos en los que la "
                          "empresa participó sin ganar, salvo las postulaciones a convocatorias.",
                          "Los datos de esta empresa son sintéticos y sirven solo para demostración."]
            if p.ruc.startswith("00") else [])
