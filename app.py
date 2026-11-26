"""API local de TrazaUNT y servidor del frontend React compilado."""
from contextlib import asynccontextmanager
import csv
from datetime import timezone
from io import StringIO
from pathlib import Path
import threading
import os
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func, or_
from sqlalchemy.exc import OperationalError

from db.database import (RUTA_BD, crear_motor, obtener_sesion, consultar_ground_truth)
from db.models import Contratacion, Entidad, Proveedor, Pago, Alerta, Bitacora
from db.seed import poblar_si_vacia
from services import seguridad, panel, operacion, predicciones
from services.convocatorias import router as convocatorias_router, sembrar_cafeteria, actualizar_escenario_cafeteria
from services.coincidencias import router as coincidencias_router, detectar_todas
from services.centro import router as centro_router
from services.empresa import router as empresa_router
from services.publico import router as publico_router
from services.cid import router as cid_router, integrar_cid
from services.integridad_api import router as integridad_router
from services.integridad import iniciar_integridad
from services.alertas_service import sincronizar, revisar
from services.trazabilidad import router as trazabilidad_router, sembrar_trazabilidad
from services.datos_publicos import sembrar_publicos, sembrar_historico

RAIZ = Path(__file__).resolve().parent


class Revision(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    estado: Literal['confirmada', 'descartada']
    estado_esperado: Literal['pendiente', 'confirmada', 'descartada']
    analista: str = Field(min_length=1, max_length=150)
    comentario: str = Field(min_length=1, max_length=4000)


def alerta_dict(a, detalle=False):
    d = dict(id=a.id, contratacion_id=a.contratacion_id, regla_id=a.regla_id,
             severidad=a.severidad, score=float(a.score), estado=a.estado,
             vigente=a.evidencia_json.get('_vigente', True),
             semaforo=a.evidencia_json.get('_priorizacion', {}).get('semaforo', 'verde'))
    if detalle:
        d.update(evidencia=a.evidencia_json, explicacion=a.explicacion)
    return d


def movimiento_dict(b):
    return dict(id=b.id, alerta_id=b.alerta_id, accion=b.accion, analista=b.analista,
                comentario=b.comentario,
                fecha=b.fecha.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('America/Lima')).isoformat())


def contrato_dict(c, entidad, proveedor, prioridad):
    return dict(id=c.id, codigo=c.codigo, entidad=entidad.nombre, entidad_id=c.entidad_id,
                proveedor=proveedor.razon_social, ruc=proveedor.ruc, proveedor_id=c.proveedor_id,
                objeto=c.objeto, monto=float(c.monto), fecha=c.fecha,
                fecha_constitucion=proveedor.fecha_constitucion, n_postores=c.n_postores,
                tipo_proceso=c.tipo_proceso, priorizacion=prioridad)


# Debe coincidir con VERSION en frontend/src/api.js: si difieren, la interfaz avisa que se reinicie.
VERSION = '5.1.0'


def crear_app(ruta_bd=None, directorio_frontend=None, acceso_local=None):
    entorno = os.getenv('TRAZA_ENTORNO', 'demo')
    if entorno not in {'demo', 'produccion'}:
        raise ValueError('TRAZA_ENTORNO debe ser demo o produccion.')
    experimentales = os.getenv('FUNCIONES_EXPERIMENTALES', '0') == '1'
    dist = Path(directorio_frontend or RAIZ / 'frontend' / 'dist')

    @asynccontextmanager
    async def lifespan(app):
        app.state.motor = crear_motor(ruta_bd)
        app.state.lock = threading.RLock()
        codigo_local = acceso_local or os.environ.get('TRAZA_ACCESO_LOCAL')
        app.state.sesiones = seguridad.Sesiones(codigo_local if entorno == 'demo' else None)
        try:
            poblar_si_vacia(app.state.motor)
            sembrar_cafeteria(app.state.motor)
            iniciar_integridad(app.state.motor)
            actualizar_escenario_cafeteria(app.state.motor)
            detectar_todas(app.state.motor)
            if entorno == "demo":
                sembrar_trazabilidad(app.state.motor)
                (sembrar_historico if ruta_bd is None else sembrar_publicos)(app.state.motor)
                integrar_cid(app.state.motor)
            if experimentales:
                predicciones.evaluar(app.state.motor)
            app.state.resultados = {r['contratacion_id']: r for r in sincronizar(app.state.motor)}
            yield
        finally:
            app.state.motor.dispose()

    app = FastAPI(title='TrazaUNT API', version=VERSION, lifespan=lifespan,
                  docs_url='/api/docs', openapi_url='/api/openapi.json', redoc_url=None)

    @app.middleware('http')
    async def peticion_local(request: Request, call_next):
        return await seguridad.proteger(request, call_next)

    app.include_router(seguridad.router)
    app.include_router(panel.router)
    app.include_router(operacion.router)
    app.state.experimentales = experimentales
    if experimentales:
        app.include_router(predicciones.router)
    app.include_router(convocatorias_router)
    app.include_router(integridad_router)
    app.include_router(trazabilidad_router)
    app.include_router(coincidencias_router)
    app.include_router(empresa_router)
    app.include_router(publico_router)
    app.include_router(cid_router)
    app.include_router(centro_router)
    app.state.entorno = entorno

    @app.get("/trazabilidad", include_in_schema=False)
    def pantalla_trazabilidad(expediente: int | None = None):
        # v5.1: la trazabilidad vive dentro de la aplicación; la página antigua solo redirige.
        return RedirectResponse("/?vista=equipo#trazabilidad" + (f"/{expediente}" if expediente else ""))

    @app.exception_handler(OperationalError)
    async def base_ocupada(request, error):
        return JSONResponse({'detail': 'La base está ocupada o no está disponible. Reintenta en unos segundos.'}, status_code=503)

    def base_contratos():
        return select(Contratacion, Entidad, Proveedor).join(Entidad).join(Proveedor)

    def filtros(q, entidad):
        f = []
        if q:
            # contains(autoescape) trata % y _ como texto, sin interpolar SQL.
            f.append(or_(Contratacion.codigo.contains(q, autoescape=True),
                         Contratacion.objeto.contains(q, autoescape=True),
                         Proveedor.razon_social.contains(q, autoescape=True)))
        if entidad:
            f.append(Contratacion.entidad_id == entidad)
        return f

    def vigentes():
        return or_(Alerta.evidencia_json['_vigente'].as_boolean().is_(None),
                   Alerta.evidencia_json['_vigente'].as_boolean().is_(True))

    @app.get('/api/health')
    @app.get('/api/salud')
    def salud():
        return {'estado': 'ok', 'frontend': 'React', 'datos': 'sintéticos', 'entorno': entorno, 'version': VERSION}

    @app.get('/api/configuracion')
    def opciones():
        from services.configuracion import cargar_configuracion
        c = cargar_configuracion()
        with obtener_sesion(app.state.motor) as s:
            entidades = [dict(id=e.id, nombre=e.nombre) for e in s.scalars(select(Entidad).order_by(Entidad.nombre))]
        return {'entorno': entorno, 'experimentales': experimentales, 'entidades': entidades, 'reglas': [{'id': k, 'nombre': v['nombre']} for k,v in c['reglas'].items()]}

    @app.get('/api/resumen')
    def resumen():
        with obtener_sesion(app.state.motor) as s:
            total = s.scalar(select(func.count()).select_from(Contratacion))
            alertas = s.scalar(select(func.count()).select_from(Alerta).where(vigentes()))
            pendientes = s.scalar(select(func.count()).select_from(Alerta).where(vigentes(), Alerta.estado == 'pendiente'))
            decisiones = s.scalar(select(func.count()).select_from(Bitacora).where(Bitacora.accion.in_(['confirmada','descartada'])))
            filas = s.execute(select(Alerta, Contratacion.codigo).join(Contratacion).where(vigentes()).order_by(Alerta.score.desc(),Alerta.id).limit(6)).all()
            prioritarias = [{**alerta_dict(a), 'codigo': codigo} for a,codigo in filas]
        return dict(contrataciones=total, alertas=alertas, pendientes=pendientes, decisiones=decisiones,
                    prioritarias=prioritarias)

    @app.get('/api/expedientes')
    def expedientes(q: str = Query('', max_length=200), entidad: int | None = Query(None, gt=0),
                    pagina: int = Query(1, ge=1), tamano: int = Query(25, ge=1, le=100)):
        stmt = base_contratos().where(*filtros(q.strip(), entidad))
        with app.state.lock, obtener_sesion(app.state.motor) as s:
            total = s.scalar(select(func.count()).select_from(stmt.subquery()))
            filas = s.execute(stmt.order_by(Contratacion.id).offset((pagina-1)*tamano).limit(tamano)).all()
            datos = [contrato_dict(c,e,p,app.state.resultados[c.id]['priorizacion']) for c,e,p in filas]
        return dict(items=datos,total=total,pagina=pagina,tamano=tamano)

    @app.get('/api/alertas')
    def alertas(q: str = Query('', max_length=200), entidad: int | None = Query(None, gt=0),
                estado: Literal['todos','pendiente','confirmada','descartada']='todos',
                severidad: Literal['todas','alta','media','baja']='todas', regla: str = Query('', max_length=60),
                pagina: int = Query(1, ge=1), tamano: int = Query(25, ge=1, le=100)):
        stmt = select(Alerta, Contratacion.codigo).join(Contratacion).join(Proveedor).where(vigentes(), *filtros(q.strip(),entidad))
        if estado != 'todos': stmt = stmt.where(Alerta.estado == estado)
        if severidad != 'todas': stmt = stmt.where(Alerta.severidad == severidad)
        if regla: stmt = stmt.where(Alerta.regla_id == regla)
        with obtener_sesion(app.state.motor) as s:
            total = s.scalar(select(func.count()).select_from(stmt.subquery()))
            filas = s.execute(stmt.order_by(Alerta.score.desc(),Alerta.id).offset((pagina-1)*tamano).limit(tamano)).all()
            items = [{**alerta_dict(a),'codigo': codigo} for a,codigo in filas]
        return dict(items=items,total=total,pagina=pagina,tamano=tamano)

    @app.get('/api/expedientes/{identificador}')
    def detalle(identificador: int):
        with app.state.lock, obtener_sesion(app.state.motor) as s:
            fila = s.execute(base_contratos().where(Contratacion.id == identificador)).first()
            if fila is None: raise HTTPException(404, 'El expediente no existe.')
            c,e,p = fila
            resultado = app.state.resultados[identificador]
            alertas = [alerta_dict(a, True) for a in s.scalars(select(Alerta).where(Alerta.contratacion_id == identificador).order_by(Alerta.id))]
            pagos = [dict(id=x.id,monto=float(x.monto),fecha_pago=x.fecha_pago,
                          tiene_conformidad=x.tiene_conformidad,tiene_comprobante=x.tiene_comprobante)
                     for x in s.scalars(select(Pago).where(Pago.contratacion_id == identificador))]
            historial = [movimiento_dict(b) for b in s.scalars(select(Bitacora).join(Alerta).where(Alerta.contratacion_id == identificador).order_by(Bitacora.id.desc()))]
            return dict(contrato=contrato_dict(c,e,p,resultado['priorizacion']), pagos=pagos,
                        alertas=alertas, historial=historial, explicacion=resultado['explicacion'], ia=resultado['ia'])

    @app.post('/api/alertas/{identificador}/revision')
    def revision(identificador: int, datos: Revision, request: Request):
        try:
            with app.state.lock:
                revisar(app.state.motor,identificador,datos.estado,request.state.usuario['nombre'],datos.comentario,datos.estado_esperado)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        return {'mensaje': 'Decisión guardada en SQLite y en la bitácora.'}

    @app.post('/api/analisis')
    def actualizar():
        with app.state.lock:
            app.state.resultados = {r['contratacion_id']:r for r in sincronizar(app.state.motor)}
        return {'mensaje': 'Análisis actualizado. Se conservaron las decisiones y el historial.'}

    @app.get('/api/historial')
    def historial(pagina: int = Query(1,ge=1),tamano: int = Query(25,ge=1,le=100)):
        with obtener_sesion(app.state.motor) as s:
            total = s.scalar(select(func.count()).select_from(Bitacora))
            items = [movimiento_dict(b) for b in s.scalars(select(Bitacora).order_by(Bitacora.id.desc()).offset((pagina-1)*tamano).limit(tamano))]
        return dict(items=items,total=total,pagina=pagina,tamano=tamano)

    @app.get('/api/metricas')
    def metricas():
        with app.state.lock, obtener_sesion(app.state.motor) as s:
            verdad = consultar_ground_truth(s)
            positivos = {i for i,r in app.state.resultados.items() if r['hallazgos']}
            tp = sum(v['es_anomalia_real'] and v['id'] in positivos for v in verdad)
            fp = sum(not v['es_anomalia_real'] and v['id'] in positivos for v in verdad)
            fn = sum(v['es_anomalia_real'] and v['id'] not in positivos for v in verdad)
            tn = len(verdad)-tp-fp-fn
        return dict(tp=tp,fp=fp,fn=fn,tn=tn,precision=tp/(tp+fp) if tp+fp else None,
                    recall=tp/(tp+fn) if tp+fn else None,tasa_fp=fp/(fp+tn) if fp+tn else None)

    @app.get('/api/exportar/{tipo}')
    def exportar(tipo: Literal['alertas','historial']):
        with obtener_sesion(app.state.motor) as s:
            if tipo == 'alertas':
                columnas = ['id','expediente','regla','score','estado','vigente']
                filas = [dict(id=a.id,expediente=codigo,regla=a.regla_id,score=float(a.score),estado=a.estado,vigente=a.evidencia_json.get('_vigente',True))
                         for a,codigo in s.execute(select(Alerta,Contratacion.codigo).join(Contratacion).order_by(Alerta.id))]
            else:
                columnas = ['id','alerta_id','accion','analista','comentario','fecha']
                filas = [movimiento_dict(b) for b in s.scalars(select(Bitacora).order_by(Bitacora.id))]
        salida = StringIO(newline='')
        escritor = csv.writer(salida, quoting=csv.QUOTE_ALL)
        escritor.writerow(columnas)
        def seguro(valor):
            texto = str(valor)
            if texto.lstrip().startswith(('=','+','-','@')) or texto.startswith(('\t','\r','\n')):
                texto = "'" + texto
            return texto
        for fila in filas: escritor.writerow([seguro(fila[k]) for k in columnas])
        return Response('\ufeff'+salida.getvalue(),media_type='text/csv',
                        headers={'Content-Disposition': f'attachment; filename="{tipo}.csv"'})

    if (dist / 'assets').is_dir():
        app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')

    @app.get('/')
    def inicio():
        if not (dist / 'index.html').is_file():
            raise HTTPException(503,'Falta compilar React: ejecuta npm ci y npm run build en frontend.')
        return FileResponse(dist / 'index.html',headers={'Cache-Control':'no-cache'})

    return app


app = crear_app()


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8000)
