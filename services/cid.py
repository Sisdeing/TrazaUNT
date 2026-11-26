"""Integración del Cuaderno de Obra Digital (CID) con identificación de procedencia.

Origen: archivos CID2022_0.xlsx, CID2025_0.xlsx y CID2026_0.xlsx de los datos abiertos del
OECE entregados al equipo. `scripts/cid_extraer.py` y `scripts/cid_compactar.py` generan
`data/publicos/cid_universidades.json.gz` con las filas de entidades universitarias.

Reglas de integración:
- Un asiento se vincula a un expediente solo si el CODIGOCONTRATO coincide exactamente con un
  contrato publicado del expediente. Nunca por nombres o montos aproximados.
- Cada asiento conserva archivo, hoja y fila de origen, y su fecha de publicación como fecha efectiva.
- Los contratistas persona natural se muestran como «dato protegido».
- La integración es idempotente: no duplica asientos si se ejecuta de nuevo.
"""
from functools import lru_cache
import gzip
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select

from db.database import obtener_sesion
from db.trazabilidad import Evento, Expediente, Fase

RUTA = Path(__file__).resolve().parents[1] / "data/publicos/cid_universidades.json.gz"
UNT = "20172557628"
VERSION = 1


@lru_cache(maxsize=1)
def cargar():
    if not RUTA.exists():
        return dict(archivos=[], contratos=[], asientos_unt={}, conjunto="Cuaderno de Obra Digital (CID)")
    with gzip.open(RUTA, "rt", encoding="utf8") as f:
        return json.load(f)


def contratos_publicados(e):
    registro = e.datos.get("registro_publico", {})
    return {str(c.get("id")) for c in registro.get("contratos_publicados", []) if c.get("id")}


def integrar_cid(motor):
    """Añade los asientos CID a la fase de ejecución del expediente con el mismo código de contrato."""
    from services.trazabilidad import evento

    datos = cargar()
    asientos = datos.get("asientos_unt", {})
    if not asientos:
        return 0
    por_codigo = {c["codigo_contrato"]: c for c in datos["contratos"]}
    total = 0
    with obtener_sesion(motor) as s:
        s.connection().exec_driver_sql("BEGIN IMMEDIATE")
        for e in s.scalars(select(Expediente).where(Expediente.propietario == "publico")):
            comunes = contratos_publicados(e) & set(asientos)
            for codigo in sorted(comunes):
                if (e.datos.get("cid") or {}).get("contrato") == codigo and e.datos["cid"].get("version") == VERSION:
                    continue
                fases = list(s.scalars(select(Fase).where(Fase.expediente_id == e.id).order_by(Fase.orden)))
                ejecucion = next((f for f in fases if f.nombre.startswith("Ejecución")), None) or next(f for f in fases if f.orden == 5)
                ya = {str(v.datos.get("numero")) for v in s.scalars(select(Evento).where(
                    Evento.expediente_id == e.id, Evento.accion == "asiento_cid"))}
                c = por_codigo[codigo]
                for a in asientos[codigo]:
                    if str(a["numero"]) in ya or not a.get("fecha"):
                        continue
                    evento(s, e, ejecucion, "importador.cid", "asiento_cid",
                           dict(origen="publico", fuente="CID", numero=a["numero"],
                                actividad=f"Asiento N° {a['numero']} del cuaderno de obra · {a['titulo']}",
                                titulo=a["titulo"], descripcion=a["descripcion"], contrato=codigo,
                                archivo=a["archivo"], hoja=a["hoja"], fila=a["fila"]),
                           "Registrado en el cuaderno de obra (fuente pública)", a["fecha"])
                    total += 1
                registro = dict(e.datos.get("registro_publico", {}))
                fuentes = [f for f in registro.get("fuentes", []) if f.get("tipo") != "Cuaderno de Obra Digital (CID)"]
                for f in c["fuentes"]:
                    fuentes.append(dict(titulo=f"{f['archivo']} · {f['hoja']} · filas {f['fila_min']}–{f['fila_max']} ({f['filas']} registros)",
                                        tipo="Cuaderno de Obra Digital (CID)", archivo=f["archivo"], fase=ejecucion.orden))
                registro["fuentes"] = fuentes
                e.datos = {**e.datos, "registro_publico": registro,
                           "cid": dict(version=VERSION, contrato=codigo, numero_contrato=c["numero_contrato"],
                                       contratista=c["contratista"], contratista_ruc=c["contratista_ruc"], monto=c["monto"],
                                       asientos=len(asientos[codigo]), primer_asiento=c["primer_asiento"],
                                       ultimo_asiento=c["ultimo_asiento"], vigencia_final=c["vigencia_final"],
                                       estado_obra=c["estado_obra"], archivo=", ".join(f["archivo"] for f in c["fuentes"]),
                                       conjunto=datos["conjunto"], generado=datos.get("generado"))}
    return total


router = APIRouter(prefix="/api/fuentes", tags=["Fuentes de información"])


def universidad(request):
    user = getattr(request.state, "usuario", None)
    if not user or user.get("rol") not in ("analista", "administrador", "auditor"):
        raise HTTPException(403, "Las fuentes detalladas se consultan desde el perfil de la universidad.")


@router.get("/catalogo")
def catalogo(request: Request):
    universidad(request)
    raiz = RUTA.parent
    leer = lambda n: json.loads((raiz / n).read_text(encoding="utf8")) if (raiz / n).exists() else {}
    ocds, complementarios, ia = leer("cobertura_ocds.json"), leer("cobertura_complementaria.json"), leer("analisis_historico.json")
    cid = cargar()
    with obtener_sesion(request.app.state.motor) as s:
        vinculados = {e.datos["cid"]["contrato"]: e.id for e in s.scalars(select(Expediente).where(Expediente.propietario == "publico"))
                      if e.datos.get("cid")}
        publicos = sum(1 for _ in s.scalars(select(Expediente.id).where(Expediente.propietario == "publico")))
    return dict(
        conjuntos=[
            dict(nombre="Contrataciones abiertas (OCDS) del OECE", tipo="Fuente pública", url="https://data.open-contracting.org/es/publication/135",
                 detalle=f"{ia.get('procedimientos_ocds', 0):,} procedimientos de {ia.get('universidades', 0)} universidades; {publicos} expedientes UNT incorporados.".replace(",", " "),
                 archivos=[dict(archivo=k, filas=v["lineas"], universidades=v["universidades"], unt=v["unt"]) for k, v in ocds.items()]),
            dict(nombre="Reportes SEACE complementarios (Excel)", tipo="Fuente pública", url=None,
                 detalle="Adjudicaciones, contratos, desiertos, comités y proveedores. Se vinculan por código exacto de convocatoria, contrato o RUC.",
                 archivos=[dict(archivo=k, filas=v["filas"], unt=v.get("vinculadas_unt", 0)) for k, v in complementarios.items() if not k.startswith("CID")]),
            dict(nombre=cid.get("conjunto", "Cuaderno de Obra Digital (CID)"), tipo="Fuente pública", url=None,
                 detalle=f"{len(cid['contratos'])} contratos de obra de universidades; {sum(len(v) for v in cid['asientos_unt'].values())} asientos de la UNT vinculados por código de contrato.",
                 archivos=[dict(archivo=a["archivo"], filas=a["filas"], universidades=a["filas_universidades"],
                                contratos=a["contratos_universidades"], unt=a["contratos_unt"]) for a in cid["archivos"]],
                 metodo=cid.get("metodo"), generado=cid.get("generado")),
            dict(nombre="Datos sintéticos de demostración", tipo="Simulada", url=None,
                 detalle="Generador con semilla 42: 600 contrataciones, convocatoria de cafetería y casos de trazabilidad. Identificados como (demo).",
                 archivos=[]),
        ],
        cid_vinculados=vinculados,
        aviso="La procedencia se conserva por registro (archivo, hoja y fila). Un dato público no equivale a una validación institucional.",
    )


@router.get("/cid")
def cid(request: Request, q: str = Query("", max_length=120), solo_unt: bool = False,
        pagina: int = Query(1, ge=1), tamano: int = Query(20, ge=1, le=100)):
    universidad(request)
    datos = cargar()
    texto = q.strip().casefold()
    filas = [c for c in datos["contratos"]
             if (not solo_unt or c["ruc_entidad"] == UNT)
             and (not texto or texto in f"{c['entidad']} {c['objeto']} {c['contratista']} {c['codigo_contrato']}".casefold())]
    inicio = (pagina - 1) * tamano
    return dict(items=filas[inicio:inicio + tamano], total=len(filas), pagina=pagina, tamano=tamano)


@router.get("/cid/{codigo}/asientos")
def asientos(codigo: str, request: Request):
    universidad(request)
    datos = cargar()
    if codigo not in datos["asientos_unt"]:
        raise HTTPException(404, "Solo se conservan los asientos de contratos de la UNT.")
    return dict(items=datos["asientos_unt"][codigo])
