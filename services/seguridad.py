"""Identidad local, sesiones opacas revocables y autorización de la API."""

from collections import deque
from datetime import datetime, timezone
import hashlib
import hmac
import os
import secrets
import threading
import time

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, select

from db.database import obtener_sesion
from db.models import Base

router = APIRouter(prefix="/api/sesion", tags=["Sesión"])
ROLES = ("administrador", "analista", "auditor", "consulta", "empresa")
# Perfiles visibles: Universidad (administrador, analista, auditor), Empresa y Público (sin cuenta).
LOCALES = {"127.0.0.1", "::1", "localhost", "testclient"}
COOKIE = "traza_sesion"
DURACION = 4 * 3600
AGREGADOS = {
    "/api/dashboard",
    "/api/configuracion",
    "/api/metricas",
    "/api/inteligencia-economica",
}


class Cuenta(Base):
    __tablename__ = "cuentas_locales"
    usuario = Column(String(80), primary_key=True)
    nombre = Column(String(150), nullable=False)
    rol = Column(String(20), nullable=False)
    clave = Column(String(200), nullable=False)


class Acceso(Base):
    __tablename__ = "auditoria_api"
    id = Column(Integer, primary_key=True)
    usuario = Column(String(80), nullable=False)
    fecha = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    metodo = Column(String(10), nullable=False)
    ruta = Column(String(300), nullable=False)
    estado = Column(Integer, nullable=False)


def derivar(clave, sal):
    return hashlib.scrypt(
        clave.encode("utf8"), salt=sal, n=2**15, r=8, p=1, maxmem=64 * 1024 * 1024
    ).hex()


def guardar_cuenta(motor, usuario, nombre, rol, clave, ruc=None):
    if rol not in ROLES or not usuario.strip() or not nombre.strip() or len(clave) < 12:
        raise ValueError(
            "Se requieren usuario, nombre, rol válido y una contraseña de 12 caracteres o más."
        )
    if (rol == "empresa") != bool(ruc):
        raise ValueError("El RUC se indica solo, y obligatoriamente, para cuentas de empresa.")
    sal = secrets.token_bytes(16)
    with obtener_sesion(motor) as s:
        if ruc:
            from db.coincidencias import CuentaEmpresa
            from db.models import Proveedor
            proveedor = s.scalar(select(Proveedor).where(Proveedor.ruc == ruc))
            if proveedor is None:
                raise ValueError("El RUC no corresponde a un proveedor registrado.")
            s.merge(CuentaEmpresa(usuario=usuario, proveedor_id=proveedor.id))
        s.merge(
            Cuenta(
                usuario=usuario,
                nombre=nombre,
                rol=rol,
                clave=sal.hex() + ":" + derivar(clave, sal),
            )
        )


class Credenciales(BaseModel):
    usuario: str = Field(min_length=1, max_length=80)
    clave: str = Field(min_length=1, max_length=240)


class AccesoLocal(BaseModel):
    codigo: str = Field(min_length=32, max_length=128)


class AccesoDemo(BaseModel):
    perfil: str = Field(pattern=r"^(universidad|administrador|empresa-(aurora|horizonte|nova))$")


PERFILES_DEMO = {
    "universidad": dict(usuario="universidad.demo", nombre="Analista de la universidad (demo)", rol="analista"),
    "administrador": dict(usuario="admin.demo", nombre="Administración de la universidad (demo)", rol="administrador"),
    "empresa-aurora": dict(usuario="empresa.aurora", ruc="00900000001"),
    "empresa-horizonte": dict(usuario="empresa.horizonte", ruc="00900000002"),
    "empresa-nova": dict(usuario="empresa.nova", ruc="00900000003"),
}


class Sesiones:
    def __init__(self, acceso_local=None):
        self.lock = threading.RLock()
        self.activas = {}
        self.intentos = {}
        self.acceso_local = acceso_local
        self.arranque = time.monotonic()

    def buscar(self, token):
        ahora = time.monotonic()
        with self.lock:
            self.activas = {k: v for k, v in self.activas.items() if v[0] > ahora}
            dato = self.activas.get(token)
        return dato[1] if dato else None

    def abrir(self, request, respuesta, usuario):
        token = secrets.token_urlsafe(32)
        with self.lock:
            self.activas.pop(request.cookies.get(COOKIE), None)
            self.activas[token] = (time.monotonic() + DURACION, usuario)
        respuesta.set_cookie(
            COOKIE,
            token,
            max_age=DURACION,
            httponly=True,
            samesite="strict",
            secure=request.url.scheme == "https" or os.getenv("TRAZA_HTTPS") == "1",
            path="/",
        )
        request.state.usuario = usuario
        return {"usuario": usuario}

    def intento(self, origen):
        ahora = time.monotonic()
        with self.lock:
            cola = self.intentos.setdefault(origen, deque(maxlen=8))
            while cola and cola[0] < ahora - 300:
                cola.popleft()
            if len(cola) == 8:
                raise HTTPException(429, "Demasiados intentos. Espera cinco minutos.")
            cola.append(ahora)


@router.get("")
def sesion(request: Request):
    return {"usuario": request.state.usuario}


@router.post("/entrar")
def entrar(datos: Credenciales, request: Request, response: Response):
    sesiones = request.app.state.sesiones
    remoto = request.client.host if request.client else "local"
    sesiones.intento(remoto)
    with obtener_sesion(request.app.state.motor) as s:
        cuenta = s.get(Cuenta, datos.usuario)
        sal, digest = cuenta.clave.split(":") if cuenta else ("00" * 16, "00" * 64)
        if (
            not hmac.compare_digest(derivar(datos.clave, bytes.fromhex(sal)), digest)
            or cuenta is None
        ):
            raise HTTPException(401, "Credenciales incorrectas.")
        usuario = dict(usuario=cuenta.usuario, nombre=cuenta.nombre, rol=cuenta.rol)
        if cuenta.rol == "empresa":
            from db.coincidencias import CuentaEmpresa
            vinculo = s.get(CuentaEmpresa, cuenta.usuario)
            if vinculo is None:
                raise HTTPException(403, "La cuenta de empresa no está vinculada a un RUC.")
            usuario["proveedor_id"] = vinculo.proveedor_id
    return sesiones.abrir(request, response, usuario)


@router.post("/demo")
def acceso_demo(datos: AccesoDemo, request: Request, response: Response):
    """Entrada por perfil para la demostración. Solo en entorno demo y desde el propio equipo."""
    remoto = request.client.host if request.client else ""
    if getattr(request.app.state, "entorno", "demo") != "demo" or remoto not in LOCALES:
        raise HTTPException(403, "El acceso de demostración solo está disponible en el equipo local.")
    perfil = dict(PERFILES_DEMO[datos.perfil])
    if "ruc" in perfil:
        from db.models import Proveedor
        with obtener_sesion(request.app.state.motor) as s:
            proveedor = s.scalar(select(Proveedor).where(Proveedor.ruc == perfil["ruc"]))
            if proveedor is None:
                raise HTTPException(404, "La empresa de demostración no existe en esta base.")
            perfil = dict(usuario=perfil["usuario"], nombre=proveedor.razon_social, rol="empresa",
                          proveedor_id=proveedor.id)
    return request.app.state.sesiones.abrir(request, response, perfil)


@router.post("/local")
def acceso_local(datos: AccesoLocal, request: Request, response: Response):
    sesiones = request.app.state.sesiones
    with sesiones.lock:
        if (
            not sesiones.acceso_local
            or time.monotonic() - sesiones.arranque > 180
            or not secrets.compare_digest(datos.codigo, sesiones.acceso_local)
        ):
            raise HTTPException(
                401, "El acceso de inicio ha caducado. Vuelve a abrir el lanzador."
            )
        sesiones.acceso_local = None
    return sesiones.abrir(
        request,
        response,
        dict(usuario="analista.local", nombre="Analista local", rol="analista"),
    )


@router.post("/salir")
def salir(request: Request, response: Response):
    sesiones = request.app.state.sesiones
    with sesiones.lock:
        sesiones.activas.pop(request.cookies.get(COOKIE), None)
    response.delete_cookie(COOKIE, path="/")
    return {"mensaje": "Sesión cerrada."}


def denegar(estado, mensaje):
    return JSONResponse(
        {"detail": mensaje}, status_code=estado, headers={"Cache-Control": "no-store"}
    )


async def proteger(request, siguiente):
    ruta = request.url.path.rstrip("/")
    if not ruta.startswith("/api/"):
        return await siguiente(request)
    escritura = request.method not in {"GET", "HEAD", "OPTIONS"}
    if escritura and request.headers.get("x-traza-client") != "react":
        return denegar(403, "Cabecera de cliente requerida.")
    usuario = request.app.state.sesiones.buscar(request.cookies.get(COOKIE))
    request.state.usuario = usuario
    publica = ruta.startswith("/api/publico/") or ruta in {
        "/api/salud",
        "/api/health",
        "/api/sesion",
        "/api/sesion/entrar",
        "/api/sesion/local",
        "/api/sesion/demo",
    }
    if not publica:
        if usuario is None:
            return denegar(401, "Inicia sesión para continuar.")
        rol = usuario["rol"]
        if ruta != "/api/sesion/salir":
            if rol == "empresa" and not (ruta == "/api/empresa" or ruta.startswith("/api/empresa/")):
                return denegar(403, "El perfil empresa solo consulta sus propias postulaciones.")
            if rol == "auditor" and (escritura or ruta not in AGREGADOS):
                return denegar(403, "El perfil auditor consulta indicadores agregados.")
            if rol == "consulta" and (
                escritura
                or ruta.startswith(
                    (
                        "/api/documentos",
                        "/api/auditoria",
                        "/api/exportar",
                        "/api/historial",
                        "/api/conflictos",
                        "/api/proveedores",
                        "/api/trazabilidad",
                        "/api/coincidencias",
                        "/api/centro-alertas",
                        "/api/fichas-empresa",
                    )
                )
            ):
                return denegar(403, "Tu perfil no tiene acceso a esta operación.")
    respuesta = await siguiente(request)
    if escritura or ruta.startswith(
        ("/api/documentos/", "/api/trazabilidad/", "/api/exportar/", "/api/proveedores/", "/api/conflictos/", "/api/empresa/", "/api/coincidencias/")
    ):
        with obtener_sesion(request.app.state.motor) as s:
            actor = request.state.usuario
            s.add(
                Acceso(
                    usuario=actor["usuario"] if actor else "anónimo",
                    metodo=request.method,
                    ruta=ruta[:300],
                    estado=respuesta.status_code,
                )
            )
    respuesta.headers.update(
        {
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        }
    )
    return respuesta
