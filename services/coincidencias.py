"""Detección automática de coincidencias entre personas y empresas.

Se ejecuta cada vez que se registra o modifica una convocatoria y cada vez que una
empresa se inscribe. Compara identificadores, nombres, domicilios, representantes y
vínculos documentados. Cada resultado es una **coincidencia para revisión**: puede
tratarse de homónimos, datos genéricos o relaciones sin incidencia en el proceso.
Ningún resultado se presenta como conflicto de intereses confirmado.
"""
from collections import Counter
from datetime import timezone
from hashlib import sha256
import re
import unicodedata
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from db.coincidencias import Coincidencia, RevisionCoincidencia, ahora
from db.convocatorias import Convocatoria, Postulacion
from db.database import obtener_sesion
from db.models import Proveedor

LIMA = ZoneInfo("America/Lima")

# Palabras que describen funciones o formas societarias: no identifican a una persona.
NO_DISTINTIVAS = {
    "demo", "de", "del", "la", "las", "los", "y", "e", "sac", "saa", "eirl", "srl", "sa",
    "representante", "titular", "socio", "socia", "evaluador", "evaluadora", "supervisor",
    "supervisora", "gerente", "comite", "persona", "prueba", "servicios", "operaciones",
    "gestion", "campus", "empresa", "consorcio", "sociedad", "anonima", "cerrada",
}

TIPOS = {
    "CI01": ("alta", "Documento de identidad coincidente",
             "El DNI de un interviniente coincide con el de una persona vinculada a una empresa postulante. "
             "Posible identidad compartida, sujeta a verificación."),
    "CI02": ("media", "Nombre completo coincidente",
             "Un interviniente y una persona vinculada a una empresa postulante tienen el mismo nombre completo. "
             "Puede tratarse de homónimos: verificar identidad antes de cualquier conclusión."),
    "CI03": ("baja", "Coincidencia parcial de apellidos",
             "Comparten al menos un apellido o término distintivo. Coincidencia débil: no indica parentesco por sí sola."),
    "CI04": ("media", "Empresas postulantes con el mismo domicilio fiscal",
             "Dos o más postulantes declaran el mismo domicilio. Requiere análisis de su independencia."),
    "CI05": ("media", "Empresas postulantes con el mismo representante",
             "Dos o más postulantes registran al mismo representante. Requiere análisis de su independencia."),
    "CI06": ("alta", "Vínculo documentado entre un interviniente y una empresa postulante",
             "Existe un registro verificado de parentesco o participación societaria. Requiere análisis contextual "
             "y verificar si hubo declaración o abstención."),
}
DECISIONES = {"aclarada": "Aclarada sin incidencia", "derivada": "Derivada a revisión de integridad"}


def normalizar(texto):
    texto = re.sub(r"\([^)]*\)", " ", str(texto or ""))
    texto = "".join(c for c in unicodedata.normalize("NFKD", texto.casefold()) if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", texto))


def distintivos(nombre):
    return {t for t in normalizar(nombre).split() if len(t) >= 3 and t not in NO_DISTINTIVAS and not t.isdigit()}


def dni_de_ruc(ruc):
    """Un RUC de persona natural (10 + DNI + verificador) contiene el DNI."""
    ruc = str(ruc or "")
    return ruc[2:10] if len(ruc) == 11 and ruc.startswith("10") else None


def _clave(cid, tipo, *partes):
    base = "|".join(sorted(normalizar(p) for p in partes))
    return f"convocatoria:{cid}:{tipo}:{sha256(base.encode()).hexdigest()[:24]}"


def personas_convocatoria(c):
    """Intervinientes internos: responsable del proceso y miembros registrados."""
    personas = [dict(nombre=c.responsable, rol="Responsable del proceso", documento=None, fuente="Ficha de la convocatoria")]
    for p in c.intervinientes or []:
        personas.append(dict(nombre=p.get("nombre"), rol=p.get("rol"), documento=p.get("documento"),
                             fuente="Intervinientes registrados en la convocatoria"))
    return [p for p in personas if p["nombre"]]


def empresas_convocatoria(s, c):
    filas = s.execute(select(Postulacion, Proveedor).join(Proveedor).where(Postulacion.convocatoria_id == c.id).order_by(Postulacion.id))
    return [(p, v) for p, v in filas]


def _domicilios_genericos(s):
    """Un domicilio repetido por más de tres empresas del registro se trata como dato genérico."""
    conteo = Counter(normalizar(d) for d in s.scalars(select(Proveedor.domicilio)))
    return {d for d, n in conteo.items() if n > 3 or not d}


def calcular(s, c):
    """Devuelve las coincidencias vigentes de una convocatoria, sin guardarlas."""
    hallazgos = {}

    def agregar(tipo, a, b, evidencia):
        nivel, titulo, detalle = TIPOS[tipo]
        clave = _clave(c.id, tipo, a["nombre"] + a.get("rol", ""), b["nombre"] + b.get("rol", ""))
        hallazgos[clave] = dict(clave=clave, tipo=tipo, nivel=nivel, titulo=titulo, detalle=detalle,
                                sujeto_a=a, sujeto_b=b, evidencia=evidencia)

    personas = personas_convocatoria(c)
    empresas = empresas_convocatoria(s, c)
    for p, v in empresas:
        empresa = dict(nombre=v.razon_social, ruc=v.ruc, rol="Empresa postulante", postulacion_id=p.id)
        vinculadas = [dict(nombre=v.representante, rol=f"Representante de {v.razon_social}", documento=None,
                           fuente="Registro del proveedor")]
        if dni_de_ruc(v.ruc):
            vinculadas.append(dict(nombre=v.razon_social, rol="Titular (persona natural)", documento=dni_de_ruc(v.ruc),
                                   fuente="RUC de persona natural"))
        for persona in personas:
            for otra in vinculadas:
                a = dict(nombre=persona["nombre"], rol=persona["rol"], fuente=persona["fuente"])
                b = dict(nombre=otra["nombre"], rol=otra["rol"], fuente=otra["fuente"], empresa=empresa)
                if persona.get("documento") and otra.get("documento") and persona["documento"] == otra["documento"]:
                    agregar("CI01", a, b, dict(campo="DNI", valor_a="••••" + persona["documento"][-4:],
                                               valor_b="••••" + otra["documento"][-4:],
                                               criterio="Igualdad exacta del documento de identidad."))
                    continue
                na, nb = normalizar(persona["nombre"]), normalizar(otra["nombre"])
                if na and na == nb and len(na.split()) >= 2:
                    agregar("CI02", a, b, dict(campo="Nombre completo", valor_a=persona["nombre"], valor_b=otra["nombre"],
                                               criterio="Igualdad del nombre normalizado (sin tildes, mayúsculas ni anotaciones)."))
                    continue
                comunes = distintivos(persona["nombre"]) & distintivos(otra["nombre"])
                if comunes:
                    agregar("CI03", a, b, dict(campo="Apellidos o términos distintivos", valor_a=persona["nombre"],
                                               valor_b=otra["nombre"], terminos=sorted(comunes),
                                               criterio="Al menos un término distintivo en común; coincidencia débil."))
    genericos = _domicilios_genericos(s)
    for i, (p1, v1) in enumerate(empresas):
        for p2, v2 in empresas[i + 1:]:
            a = dict(nombre=v1.razon_social, ruc=v1.ruc, rol="Empresa postulante", fuente="Registro del proveedor")
            b = dict(nombre=v2.razon_social, ruc=v2.ruc, rol="Empresa postulante", fuente="Registro del proveedor")
            d1 = normalizar(v1.domicilio)
            if d1 and d1 == normalizar(v2.domicilio) and d1 not in genericos:
                agregar("CI04", a, b, dict(campo="Domicilio fiscal", valor_a=v1.domicilio, valor_b=v2.domicilio,
                                           criterio="Igualdad del domicilio normalizado; se excluyen domicilios genéricos repetidos en el registro."))
            r1 = normalizar(v1.representante)
            if r1 and r1 == normalizar(v2.representante) and distintivos(v1.representante):
                agregar("CI05", a, b, dict(campo="Representante", valor_a=v1.representante, valor_b=v2.representante,
                                           criterio="Igualdad del nombre normalizado del representante."))
    try:
        from services.integridad import casos
        postulantes = {v.id for _, v in empresas}
        for caso in casos(s, proceso=c.codigo):
            if caso["proveedor_id"] not in postulantes:
                continue
            a = dict(nombre=caso["servidor"], rol=caso["rol"], fuente="Registro de intervinientes")
            b = dict(nombre=caso["familiar"], rol=f"{caso['cargo']} de {caso['proveedor']}", fuente="Registro de vínculos",
                     empresa=dict(nombre=caso["proveedor"], ruc=caso["ruc"]))
            agregar("CI06", a, b, dict(campo="Vínculo registrado", parentesco=caso["parentesco"], grado=caso["grado"],
                                       referencia=caso["evidencia"], desde=caso["desde"],
                                       reglas=[f"{x['regla']}: {x['motivo']}" for x in caso["senales"]],
                                       declaracion=caso["estado"],
                                       criterio="Vínculo verificado vigente en el registro de integridad."))
    except Exception:  # El registro de vínculos es opcional: su ausencia no impide las demás comparaciones.
        pass
    return hallazgos


def detectar_convocatoria(s, c):
    """Guarda las coincidencias nuevas, actualiza su vigencia y conserva las anteriores."""
    actuales = calcular(s, c)
    existentes = {x.clave: x for x in s.scalars(select(Coincidencia).where(Coincidencia.ambito == "convocatoria",
                                                                         Coincidencia.referencia_id == c.id))}
    nuevas = []
    for clave, h in actuales.items():
        x = existentes.get(clave)
        if x is None:
            x = Coincidencia(ambito="convocatoria", referencia_id=c.id, **h)
            s.add(x)
            nuevas.append(x)
        else:
            x.evidencia, x.sujeto_a, x.sujeto_b = h["evidencia"], h["sujeto_a"], h["sujeto_b"]
            if not x.vigente:
                x.vigente = True
            x.actualizada = ahora()
    for clave, x in existentes.items():
        if clave not in actuales and x.vigente:
            x.vigente = False
            x.actualizada = ahora()
    s.flush()
    return nuevas


def detectar_todas(motor):
    with obtener_sesion(motor) as s:
        for c in s.scalars(select(Convocatoria)):
            detectar_convocatoria(s, c)


def _fecha(dt):
    return dt.replace(tzinfo=timezone.utc).astimezone(LIMA).isoformat() if dt else None


def ficha(x, revisiones=None, convocatoria=None):
    nivel = dict(alta="Alta", media="Media", baja="Baja")[x.nivel]
    return dict(id=x.id, ambito=x.ambito, referencia_id=x.referencia_id, tipo=x.tipo, nivel=x.nivel,
                nivel_texto=nivel, titulo=x.titulo, detalle=x.detalle, sujeto_a=x.sujeto_a, sujeto_b=x.sujeto_b,
                evidencia=x.evidencia, estado=x.estado, estado_texto=DECISIONES.get(x.estado, "Pendiente de revisión"),
                vigente=x.vigente, detectada=_fecha(x.detectada), actualizada=_fecha(x.actualizada),
                convocatoria=convocatoria,
                aviso="Coincidencia para revisión. No constituye un conflicto de intereses confirmado.",
                revisiones=[dict(decision=r.decision, decision_texto=DECISIONES[r.decision], justificacion=r.justificacion,
                                 autor=r.autor, fecha=_fecha(r.fecha)) for r in (revisiones or [])])


def resumen_convocatoria(s, cid):
    filas = list(s.scalars(select(Coincidencia).where(Coincidencia.ambito == "convocatoria", Coincidencia.referencia_id == cid,
                                                      Coincidencia.vigente.is_(True)).order_by(Coincidencia.id)))
    orden = {"alta": 0, "media": 1, "baja": 2}
    return [ficha(x) for x in sorted(filas, key=lambda x: (orden[x.nivel], x.id))]


def universidad(request: Request):
    user = getattr(request.state, "usuario", None)
    if not user:
        raise HTTPException(401, "Inicia sesión para acceder.")
    if user.get("rol") not in ("analista", "administrador"):
        raise HTTPException(403, "Las coincidencias se revisan desde el perfil de la universidad.")
    return user


router = APIRouter(prefix="/api", tags=["Coincidencias"], dependencies=[Depends(universidad)])


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    decision: str = Field(pattern="^(aclarada|derivada)$")
    justificacion: str = Field(min_length=15, max_length=2000)


@router.get("/coincidencias")
def listar(request: Request, estado: str = Query("pendiente", pattern="^(pendiente|revisadas|todas)$"),
           vigentes: bool = Query(True)):
    with obtener_sesion(request.app.state.motor) as s:
        q = select(Coincidencia, Convocatoria).join(Convocatoria, Convocatoria.id == Coincidencia.referencia_id)
        if vigentes:
            q = q.where(Coincidencia.vigente.is_(True))
        if estado == "pendiente":
            q = q.where(Coincidencia.estado == "pendiente")
        elif estado == "revisadas":
            q = q.where(Coincidencia.estado != "pendiente")
        orden = {"alta": 0, "media": 1, "baja": 2}
        filas = sorted(s.execute(q), key=lambda f: (orden[f[0].nivel], -f[0].id))
        conteo = Counter(x.nivel for x, _ in filas)
        return dict(items=[ficha(x, convocatoria=dict(id=c.id, codigo=c.codigo, nombre=c.nombre)) for x, c in filas],
                    por_nivel=dict(alta=conteo["alta"], media=conteo["media"], baja=conteo["baja"]),
                    total=len(filas))


@router.get("/coincidencias/{identificador}")
def ver(identificador: int, request: Request):
    with obtener_sesion(request.app.state.motor) as s:
        x = s.get(Coincidencia, identificador)
        if x is None:
            raise HTTPException(404, "Coincidencia no localizada.")
        c = s.get(Convocatoria, x.referencia_id)
        revs = list(s.scalars(select(RevisionCoincidencia).where(RevisionCoincidencia.coincidencia_id == x.id).order_by(RevisionCoincidencia.id)))
        return ficha(x, revs, dict(id=c.id, codigo=c.codigo, nombre=c.nombre) if c else None)


@router.post("/coincidencias/{identificador}/revision")
def revisar(identificador: int, datos: Decision, request: Request):
    user = universidad(request)
    with obtener_sesion(request.app.state.motor) as s:
        s.connection().exec_driver_sql("BEGIN IMMEDIATE")
        x = s.get(Coincidencia, identificador)
        if x is None:
            raise HTTPException(404, "Coincidencia no localizada.")
        if not x.vigente:
            raise HTTPException(409, "La coincidencia ya no está vigente; se conserva solo como historial.")
        if x.estado == datos.decision:
            raise HTTPException(409, "La coincidencia ya tiene esa decisión registrada.")
        s.add(RevisionCoincidencia(coincidencia_id=x.id, decision=datos.decision, justificacion=datos.justificacion,
                                   autor=user["nombre"], cuenta=user["usuario"]))
        x.estado = datos.decision
        x.actualizada = ahora()
        s.flush()
        from db.convocatorias import EventoConvocatoria
        s.add(EventoConvocatoria(convocatoria_id=x.referencia_id, autor=user["nombre"], accion="revision_coincidencia",
                                 motivo=f"{x.tipo} · {DECISIONES[datos.decision]}: {datos.justificacion}",
                                 datos=dict(coincidencia_id=x.id, decision=datos.decision)))
        revs = list(s.scalars(select(RevisionCoincidencia).where(RevisionCoincidencia.coincidencia_id == x.id).order_by(RevisionCoincidencia.id)))
        c = s.get(Convocatoria, x.referencia_id)
        return ficha(x, revs, dict(id=c.id, codigo=c.codigo, nombre=c.nombre))


def conteo_pendientes(s):
    return s.scalar(select(func.count()).select_from(Coincidencia).where(Coincidencia.vigente.is_(True),
                                                                         Coincidencia.estado == "pendiente")) or 0
