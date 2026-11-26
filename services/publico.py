"""Perfil Público: transparencia sin cuenta.

Publica estados, fechas, fases, documentos (nombre, versión y huella SHA-256) y fuentes.
No publica nombres de personas, responsables, observaciones en texto libre, postores
personas naturales, padrón, alertas individuales ni coincidencias.
"""
from collections import Counter, defaultdict

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import func, select

from db.convocatorias import Convocatoria, Postulacion
from db.database import obtener_sesion
from db.models import Proveedor
from db.trazabilidad import AlertaTZ, DocumentoTZ, Evento, Expediente, Fase

router = APIRouter(prefix="/api/publico", tags=["Consulta pública"])

ACTIVIDADES = {
    "crear_expediente": "Expediente registrado", "importar_registro": "Registro público incorporado",
    "iniciar": "Fase iniciada", "cargar_documento": "Documento incorporado", "verificar": "Requisito verificado",
    "observar": "Observación registrada", "subsanar": "Subsanación presentada", "cerrar_observacion": "Observación cerrada",
    "visto_bueno": "Visto bueno registrado", "pago": "Pago registrado", "cerrar": "Fase cerrada",
    "reabrir": "Fase reabierta", "asignar": "Responsable asignado", "revision_alerta": "Alerta revisada por la universidad",
}
ESTADOS_CONV = {"borrador": "En preparación", "abierta": "Recepción abierta", "cerrada": "Recepción cerrada",
                "en_evaluacion": "En evaluación", "resultado_registrado": "Resultado registrado", "cancelada": "Cancelada"}


def procedencia(e):
    if e.propietario == "publico" or e.datos.get("origen") == "publico":
        return "publica", "Fuente pública (OECE / SEACE)"
    if e.propietario == "demo" or e.datos.get("sintetico"):
        return "demo", "Caso sintético de demostración"
    return "local", "Registro de la universidad"


def actividad(v):
    if v.accion == "hecho_publicado":
        return v.datos.get("actividad") or "Hecho publicado"
    if v.accion == "asiento_cid":
        return f"Asiento N° {v.datos.get('numero')} del cuaderno de obra digital"
    if v.accion == "cargar_documento":
        return f"Documento incorporado (versión {v.datos.get('version', 1)})"
    if v.accion == "pago" and v.datos.get("pagado"):
        return f"Pago registrado por S/ {v.datos['pagado']}"
    return ACTIVIDADES.get(v.accion)


def fuente_evento(v):
    if v.accion == "asiento_cid":
        return f"{v.datos.get('archivo')} · fila {v.datos.get('fila')}"
    if v.accion in ("hecho_publicado", "importar_registro"):
        return "Registro público"
    return "Registro de la universidad"


@router.get("/convocatorias")
def convocatorias(request: Request):
    with obtener_sesion(request.app.state.motor) as s:
        cuentas = Counter(s.scalars(select(Postulacion.convocatoria_id)))
        items = []
        for c in s.scalars(select(Convocatoria).where(Convocatoria.estado != "borrador").order_by(Convocatoria.id.desc())):
            ganador = None
            if c.resultado:
                p = s.get(Postulacion, c.resultado.get("postulante_id"))
                v = s.get(Proveedor, p.proveedor_id) if p else None
                natural = bool(v and v.ruc.startswith("10"))
                ganador = None if v is None else ("Persona natural (dato protegido)" if natural else v.razon_social)
            items.append(dict(codigo=c.codigo, nombre=c.nombre.removesuffix(" — DEMO"), modalidad=c.modalidad, area=c.area,
                              estado=c.estado, estado_texto=ESTADOS_CONV.get(c.estado, c.estado),
                              apertura=c.apertura.isoformat(), cierre=c.cierre.isoformat(),
                              importe_referencial=float(c.presupuesto), postulantes=cuentas[c.id], resultado=ganador))
        return dict(items=items, aviso="Convocatorias de demostración. No se publican datos de personas.")


@router.get("/expedientes")
def expedientes(request: Request, q: str = Query("", max_length=120),
                procedencia_filtro: str = Query("", alias="procedencia", pattern="^(|publica|demo|local)$"),
                pagina: int = Query(1, ge=1), tamano: int = Query(20, ge=1, le=50)):
    with obtener_sesion(request.app.state.motor) as s:
        fases = defaultdict(list)
        for f in s.execute(select(Fase.expediente_id, Fase.estado)):
            fases[f[0]].append(f[1])
        eventos = dict(s.execute(select(Evento.expediente_id, func.count()).group_by(Evento.expediente_id)).all())
        consulta = select(Expediente).order_by(Expediente.id.desc())
        texto_q = q.strip().casefold()
        filas = []
        for e in s.scalars(consulta):
            registro = e.datos.get("registro_publico", {})
            if texto_q and texto_q not in f"{e.codigo} {e.nombre} {registro.get('codigo_convocatoria', '')} {registro.get('id_fuente', '')} {registro.get('nombre', '')}".casefold():
                continue
            clave, texto = procedencia(e)
            if procedencia_filtro and clave != procedencia_filtro:
                continue
            fs = fases[e.id]
            filas.append(dict(id=e.id, codigo=e.codigo, nombre=e.nombre, referencia=registro.get('nombre') or registro.get('codigo_convocatoria'), tipo=e.tipo, monto=e.monto, inicio=e.inicio,
                              procedencia=clave, procedencia_texto=texto, fases_cerradas=sum(x == "cerrada" for x in fs),
                              fases=len(fs), actuaciones=eventos.get(e.id, 0), cuaderno_obra=bool(e.datos.get("cid"))))
        inicio = (pagina - 1) * tamano
        return dict(items=filas[inicio:inicio + tamano], total=len(filas), pagina=pagina, tamano=tamano,
                    por_procedencia=dict(Counter(x["procedencia"] for x in filas)))


@router.get("/expedientes/{eid}")
def expediente(eid: int, request: Request):
    with obtener_sesion(request.app.state.motor) as s:
        e = s.get(Expediente, eid)
        if e is None:
            raise HTTPException(404, "Expediente no localizado.")
        fs = list(s.scalars(select(Fase).where(Fase.expediente_id == eid).order_by(Fase.orden)))
        nombres = {f.id: f.nombre for f in fs}
        evs = list(s.scalars(select(Evento).where(Evento.expediente_id == eid).order_by(Evento.efectiva, Evento.id)))
        docs = list(s.scalars(select(DocumentoTZ).where(DocumentoTZ.fase_id.in_(list(nombres))).order_by(DocumentoTZ.id)))
        alertas = list(s.scalars(select(AlertaTZ).where(AlertaTZ.expediente_id == eid, AlertaTZ.vigente.is_(True))))
        por_fase = defaultdict(list)
        for v in evs:
            por_fase[v.fase_id].append(v)
        clave, texto = procedencia(e)
        registro = e.datos.get("registro_publico", {})
        cid = e.datos.get("cid")
        return dict(
            id=e.id, codigo=e.codigo, nombre=e.nombre, objeto=e.objeto, tipo=e.tipo, monto=e.monto, inicio=e.inicio,
            area=e.area, procedencia=clave, procedencia_texto=texto,
            codigo_convocatoria=registro.get("codigo_convocatoria"), referencia=registro.get("nombre"),
            fases=[dict(orden=f.orden, codigo=f.codigo, nombre=f.nombre, estado=f.estado,
                        desde=min((v.efectiva[:10] for v in por_fase[f.id]), default=None),
                        hasta=max((v.efectiva[:10] for v in por_fase[f.id]), default=None),
                        actuaciones=len(por_fase[f.id]), documentos=sum(d.fase_id == f.id for d in docs)) for f in fs],
            cronologia=[dict(fecha=v.efectiva[:10], fase=nombres.get(v.fase_id), actividad=actividad(v), fuente=fuente_evento(v))
                        for v in evs if actividad(v)],
            documentos=[dict(fase=nombres[d.fase_id], nombre=d.nombre, version=d.version, sha256=d.sha256, fecha=d.fecha[:10])
                        for d in docs],
            fuentes=[dict(titulo=f.get("titulo"), url=f.get("url"), tipo=f.get("tipo"))
                     for f in registro.get("fuentes", []) if str(f.get("url", "")).startswith("https://") or f.get("archivo")],
            cuaderno_obra=dict(contrato=cid["contrato"], numero_contrato=cid.get("numero_contrato"),
                               contratista=cid.get("contratista"), asientos=cid["asientos"], primer_asiento=cid["primer_asiento"],
                               ultimo_asiento=cid["ultimo_asiento"], vigencia_final=cid.get("vigencia_final"),
                               archivo=cid["archivo"], conjunto=cid["conjunto"]) if cid else None,
            alertas=dict(vigentes=len(alertas), atendidas=sum(a.estado != "pendiente" for a in alertas)),
            aviso="Vista pública: se omiten nombres de personas, observaciones en texto libre y alertas individuales.",
        )
