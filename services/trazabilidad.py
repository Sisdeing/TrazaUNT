"""Flujo transaccional de expedientes y análisis explicable. Datos demo sintéticos."""
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from collections import Counter
from pathlib import Path
from functools import lru_cache
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from db.database import obtener_sesion
from db.trazabilidad import Expediente, Fase, Requisito, DocumentoTZ, Observacion, Evento, AlertaTZ
from db.models import Contratacion, Proveedor
from db.convocatorias import Convocatoria
from db.integridad import Concesion
from services.trazadocs import validar_archivo, MAX_BYTES

router=APIRouter(prefix='/api/trazabilidad',tags=['Expedientes y trazabilidad'])
PLANTILLAS={
 'servicios': [('REQ','Requerimiento',['Términos de referencia','Justificación y presupuesto']),('PRE','Actuaciones preparatorias',['Sustento de mercado','Disponibilidad presupuestaria']),('SEL','Convocatoria y selección',['Bases y cronograma','Acta de evaluación']),('CTR','Adjudicación y contratación',['Contrato','Sustento de adjudicación']),('EJE','Ejecución contractual',['Informe de entregables']),('CNF','Conformidad',['Informe de conformidad']),('PAG','Pago',['Comprobante y autorización']),('CIE','Cierre',['Informe final'])],
 'concesion': [('REQ','Necesidad y condiciones',['Informe de necesidad']),('PRE','Preparación',['Bases y condiciones']),('SEL','Selección',['Acta de evaluación']),('CTR','Formalización',['Contrato de concesión']),('EJE','Inspecciones y obligaciones',['Informe de inspección']),('CNF','Verificación',['Informe de obligaciones']),('PAG','Contraprestaciones',['Comprobante de abono a la UNT']),('CIE','Cierre o renovación',['Informe final y garantías'])]}

# Plantillas orientativas: no sustituyen el régimen aplicable ni acreditan el cumplimiento.
for tipo, requisito, entregable in [('bienes','Especificaciones técnicas','Acta de entrega de bienes'),('obras','Expediente técnico','Valorización e informe de obra'),('otros','Documento de necesidad','Evidencia de ejecución')]:
    PLANTILLAS[tipo]=[(pref,nombre,([requisito,'Justificación y presupuesto'] if pref=='REQ' else [entregable] if pref=='EJE' else list(reqs))) for pref,nombre,reqs in PLANTILLAS['servicios']]

# Cuentas del generador de casos sintéticos: representan áreas distintas, no a una persona.
ACTORES_SEMILLA={'registro.demo','aprobador.demo','tesoreria.demo','verificador.demo','demo'}
def ahora(): return datetime.now(timezone.utc).isoformat()
def error(msg,code=409): raise HTTPException(code,msg)
def lista(s,cls,**kw): return list(s.scalars(select(cls).filter_by(**kw).order_by(cls.id)))
def dictrow(x,omit=()): return {c.name:getattr(x,c.name) for c in x.__table__.columns if c.name not in omit}
def acceso(s,r,eid,write=False):
    e=s.get(Expediente,eid)
    if not e: error('Expediente no localizado.',404)
    u=r.state.usuario
    if u['rol']!='administrador' and e.propietario not in (u['usuario'],'demo','publico') and u['usuario'] not in e.datos.get('colaboradores',[]): error('Sin permiso sobre este expediente.',403)
    if write and u['rol'] not in ('administrador','analista'): error('Perfil de solo lectura.',403)
    return e

def actor(r): return r.state.usuario['usuario']
def nombre(r): return r.state.usuario.get('nombre') or r.state.usuario['usuario']
def evento(s,e,f,a,accion,d,resp=None,fecha=None):
    prev=s.scalar(select(Evento).where(Evento.expediente_id==e.id).order_by(Evento.id.desc()).limit(1))
    t=ahora(); efectiva=fecha or t
    payload=[e.id,f.id if f else None,a,resp or a,accion,t,efectiva,d,prev.hash if prev else 'GENESIS']
    ev=Evento(expediente_id=e.id,fase_id=f.id if f else None,actor=a,responsable=resp or a,accion=accion,fecha=t,efectiva=efectiva,datos=d,hash=sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest());s.add(ev);s.flush();return ev

def crear(s,d,a):
    for campo,cls in [('convocatoria_id',Convocatoria),('contratacion_id',Contratacion),('concesion_id',Concesion),('proveedor_id',Proveedor)]:
        v=d.get(campo)
        if v and not s.get(cls,v): error('Referencia no localizada: '+campo,422)
        if v and campo!='proveedor_id' and s.scalar(select(Expediente.id).filter_by(**{campo:v})): error('La referencia ya tiene expediente.')
    # BEGIN IMMEDIATE serializa asignación de código y cambios concurrentes.
    n=(s.scalar(select(func.max(Expediente.id))) or 0)+1; year=date.today().year
    e=Expediente(id=n,codigo=f'EXP-UNT-{year}-{n:06d}',nombre=d['nombre'],objeto=d['objeto'],tipo=d['tipo'],area=d['area'],responsable=d['responsable'],inicio=d['inicio'],monto=d['monto'],propietario=a,plantilla={'version':1,'fases':PLANTILLAS[d['tipo']]},datos=d.get('datos',{}),**{k:d.get(k) for k in ('convocatoria_id','contratacion_id','concesion_id','proveedor_id')});s.add(e);s.flush()
    for i,(p,nombre,reqs) in enumerate(PLANTILLAS[e.tipo],1):
        f=Fase(expediente_id=e.id,codigo=f'{p}-{year}-{e.id:06d}-{i:02d}',orden=i,nombre=nombre,estado='pendiente',responsable=e.responsable,limite=(date.fromisoformat(e.inicio)+timedelta(days=i*7)).isoformat(),revision=0);s.add(f);s.flush()
        for req in reqs:s.add(Requisito(fase_id=f.id,nombre=req,estado='pendiente',obligatorio=True))
    evento(s,e,None,a,'crear_expediente',{'plantilla':1});return e

class Nuevo(BaseModel):
    nombre:str=Field(min_length=1,max_length=200);objeto:str=Field(min_length=1,max_length=4000)
    area:str=Field(min_length=1,max_length=150);responsable:str=Field(min_length=1,max_length=150)
    tipo:str='servicios';inicio:date;monto:Decimal=Field(ge=0,max_digits=14,decimal_places=2)
    convocatoria_id:int|None=None;contratacion_id:int|None=None;concesion_id:int|None=None;proveedor_id:int|None=None
    datos:dict=Field(default_factory=dict)
class Accion(BaseModel):
    accion:str;revision:int=Field(ge=0);justificacion:str=Field(min_length=1,max_length=4000)
    requisito_id:int|None=None;documento_id:int|None=None;observacion_id:int|None=None
    responsable:str=Field(default='',max_length=150);limite:date|None=None;severidad:str='media'
    monto_autorizado:Decimal|None=None;monto_pagado:Decimal|None=None

@router.get('')
def expedientes(request:Request):
    with obtener_sesion(request.app.state.motor) as s:
        out=[]
        for e in lista(s,Expediente):
            try: acceso(s,request,e.id)
            except HTTPException: continue
            fs=lista(s,Fase,expediente_id=e.id); als=lista(s,AlertaTZ,expediente_id=e.id)
            data=dictrow(e); data['datos']=dict(e.datos);
            if 'registro_publico' in data['datos']:
                r=data['datos']['registro_publico'];data['datos']['registro_publico']={k:r.get(k) for k in ('id_fuente','codigo_convocatoria','modalidad')}
            out.append({**data,'avance':round(100*sum(f.estado=='cerrada' for f in fs)/len(fs)), 'alertas':sum(a.vigente and a.estado=='pendiente' for a in als),'fases_vencidas':sum(bool(f.limite) and f.limite<date.today().isoformat() and f.estado!='cerrada' for f in fs)})
        return {'items':out}
@router.post('')
def nuevo(d:Nuevo,request:Request):
    if request.state.usuario['rol'] not in ('administrador','analista'): error('Perfil de solo lectura.',403)
    if d.tipo not in PLANTILLAS: error('Tipo no admitido.',422)
    with obtener_sesion(request.app.state.motor) as s:
        s.connection().exec_driver_sql('BEGIN IMMEDIATE');datos=d.model_dump(mode='json');datos['datos']={k:v for k,v in datos['datos'].items() if k not in ('origen','sintetico','registro_publico')};e=crear(s,datos,actor(request));return {'id':e.id,'codigo':e.codigo}

def analizar(s,e):
    fs=lista(s,Fase,expediente_id=e.id); evs=lista(s,Evento,expediente_id=e.id); found={}
    def add(reg,f,desc,ev=None,origin=None,extra=None):
        clave=f'{e.id}:{f.id}:{reg}:{ev.id if ev else 0}:{extra or ""}'
        found[clave]=(reg,f,desc,ev,{'origen_fase_id':(origin or f).id,'evento_id':ev.id if ev else None,'detalle':extra})
    for f in fs:
        obs=lista(s,Observacion,fase_id=f.id); req=lista(s,Requisito,fase_id=f.id); es=[v for v in evs if v.fase_id==f.id]
        avanz=f.estado in ('validada','cerrada')
        if avanz:
            for q in req:
                if q.obligatorio and q.estado!='validado': add('TZ02',f,'Requisito obligatorio sin validar: '+q.nombre,extra=q.id)
            if any(o.estado!='cerrada' for o in obs):add('TZ05',f,'Observación pendiente en fase avanzada.')
            if not any(v.accion=='verificar' for v in es):add('TZ11',f,'Avance sin verificación registrada.')
        if f.estado!='cerrada' and bool(f.limite) and f.limite<date.today().isoformat():add('TZ08',f,'Plazo de fase vencido.')
        for v in es:
            if v.accion in ('visto_bueno','cerrar') and not any(w.accion=='verificar' and w.id<v.id for w in es):add('TZ11',f,'Visto bueno o cierre sin verificación previa.',v)
            if v.accion=='pago':
                cnf=next((x for x in fs if x.orden==6),None)
                if cnf and (not any(w.fase_id==cnf.id and w.accion=='cerrar' and w.id<v.id for w in evs) or v.datos.get('observaciones_conformidad')):add('TZ04',f,'Pago registrado sin conformidad libre de observaciones requeridas.',v,cnf)
                if Decimal(v.datos['pagado'])!=Decimal(v.datos['autorizado']):add('TZ09',f,'Monto pagado distinto del autorizado.',v)
                try:contrato=Decimal(e.monto) if e.monto else None
                except InvalidOperation:contrato=None
                if contrato and contrato>0 and Decimal(v.datos['pagado'])>contrato:add('TZ09',f,f'Monto pagado (S/ {v.datos["pagado"]}) supera el monto registrado del expediente (S/ {contrato}).',v,extra='supera_monto')
        if sum(v.accion=='reabrir' for v in es)>1:add('TZ14',f,'Reaperturas reiteradas.')
        for doc in lista(s,DocumentoTZ,fase_id=f.id):
            if sha256(doc.contenido).hexdigest()!=doc.sha256:add('TZ13',f,'Hash documental no coincide.',extra=doc.id)
        if f.estado not in ('pendiente','cancelada'):
            prev=next((x for x in fs if x.orden==f.orden-1),None)
            if prev and prev.estado!='cerrada':add('TZ01',f,'Fase anterior no cerrada.',origin=prev)
    # TZ06: la misma cuenta interviene en funciones que deberían estar separadas.
    # Es una coincidencia para revisión: no prueba un conflicto ni una irregularidad.
    por_orden={f.orden:f for f in fs}
    def cuentas(orden,acciones):
        f=por_orden.get(orden)
        return {v.actor:v for v in evs if f and v.fase_id==f.id and v.accion in acciones and v.actor not in ACTORES_SEMILLA and not v.actor.startswith('importador')}
    funciones={1:('formula el requerimiento',{'iniciar','cargar_documento'}),6:('otorga la conformidad',{'visto_bueno','cerrar'}),7:('registra el pago',{'pago'})}
    for a_ord,b_ord in ((1,6),(6,7),(1,7)):
        if a_ord not in por_orden or b_ord not in por_orden:continue
        primero=cuentas(a_ord,funciones[a_ord][1]);segundo=cuentas(b_ord,funciones[b_ord][1])
        for cuenta in sorted(set(primero)&set(segundo)):
            add('TZ06',por_orden[b_ord],f'La misma cuenta ({cuenta}) {funciones[a_ord][0]} y {funciones[b_ord][0]}. Coincidencia de funciones para revisión.',segundo[cuenta],por_orden[a_ord],f'{a_ord}-{b_ord}:{cuenta}')
    existing={a.clave:a for a in lista(s,AlertaTZ,expediente_id=e.id)}
    for k,a in existing.items():a.vigente=k in found
    for k,(reg,f,desc,ev,evdata) in found.items():
        if k not in existing:s.add(AlertaTZ(expediente_id=e.id,fase_id=f.id,evento_id=ev.id if ev else None,clave=k,regla=reg,descripcion=desc,evidencia=evdata,fecha=ahora(),estado='pendiente',vigente=True))
    s.flush()

@lru_cache(maxsize=1)
def indice_padron_publico():
    ruta=Path(__file__).resolve().parents[1]/'data/publicos/padron_unt.json'
    idx={}
    if ruta.exists():
        for row in json.loads(ruta.read_text(encoding='utf8')):
            k=str(row['datos'].get('RUC PROVEEDOR') or '').strip().removesuffix('.0')
            if k:idx.setdefault(k,[]).append(row)
    return idx

def padron_expediente(e):
    r=e.datos.get('registro_publico',{});ids=set()
    for q in r.get('postores',[]):
        id=str(q.get('id') or '')
        if id.startswith('PE-RUC-'):ids.add(id.removeprefix('PE-RUC-'))
    for q in r.get('registros_complementarios',[]):
        for k in ('RUC PROVEEDOR','RUC_CONTRATISTA'):
            v=q['datos'].get(k)
            if v:ids.add(str(v).strip().removesuffix('.0'))
    idx=indice_padron_publico();return [x for k in sorted(ids) for x in idx.get(k,[])]

PROTEGIDO='Persona natural (dato protegido)'
def _natural(ruc): return str(ruc or '').removeprefix('PE-RUC-').startswith('10')
def proteger_personas(datos):
    """Oculta nombres de personas naturales (RUC 10) y del comité en la vista; el registro original se conserva."""
    r=datos.get('registro_publico')
    if not r:return datos
    r=dict(r)
    r['postores']=[{**q,'id':'PE-RUC-10•••••••••','nombre':PROTEGIDO} if _natural(q.get('id')) else q for q in r.get('postores',[])]
    r['proveedores']=[PROTEGIDO if any(_natural(q.get('id')) and q.get('nombre')==p for q in datos['registro_publico'].get('postores',[])) else p for p in r.get('proveedores',[])]
    if r.get('comite'):r['comite']=[f'{len(r["comite"])} miembro(s) publicados en la fuente (nombres protegidos en la vista)']
    complementarios=[]
    for x in r.get('registros_complementarios',[]):
        d=dict(x.get('datos',{}))
        for k in ('RUC PROVEEDOR','RUC_CONTRATISTA'):
            if _natural(str(d.get(k,'')).removesuffix('.0')):
                d[k]='10•••••••••';d={c:(PROTEGIDO if any(t in c for t in ('PROVEEDOR','CONTRATISTA','NOMBRE','POSTOR')) and c!=k else v) for c,v in d.items()}
        for c in list(d):
            if any(t in c.upper() for t in ('MIEMBRO','NOMBRES','APELLIDO','DNI')):d[c]='Dato protegido'
        complementarios.append({**x,'datos':d})
    r['registros_complementarios']=complementarios
    return {**datos,'registro_publico':r}

def detalle(s,e):
    fs=lista(s,Fase,expediente_id=e.id); es=lista(s,Evento,expediente_id=e.id); seq=[x.accion for x in es]; edges=Counter(zip(seq,seq[1:])); out=[]
    for f in fs:
        req=lista(s,Requisito,fase_id=f.id)
        out.append({**dictrow(f),'requisitos':[dictrow(q) for q in req],'documentos':[dictrow(x,('contenido',)) for x in lista(s,DocumentoTZ,fase_id=f.id)],'observaciones':[dictrow(x) for x in lista(s,Observacion,fase_id=f.id)],'avance':round(100*sum(q.estado=='validado' for q in req)/max(1,len(req)))})
    return {**dictrow(e),'datos':proteger_personas(e.datos),'padron_publicado':[x for x in padron_expediente(e) if not _natural(str(x['datos'].get('RUC PROVEEDOR','')).removesuffix('.0'))],'fases':out,'eventos':[dictrow(x) for x in es],'alertas':[dictrow(x) for x in lista(s,AlertaTZ,expediente_id=e.id)],'mineria':{'metodo':'Grafo de sucesión directa de actividades registradas','transiciones':[{'desde':a,'hasta':b,'frecuencia':n} for (a,b),n in edges.items()]}}
@router.get('/historico')
def historico(request:Request):
    raiz=Path(__file__).resolve().parents[1]/'data/publicos'
    return {k:json.loads((raiz/f'{v}.json').read_text(encoding='utf8')) if (raiz/f'{v}.json').exists() else {} for k,v in [('ocds','cobertura_ocds'),('complementarios','cobertura_complementaria'),('ia','analisis_historico')]}

@router.get('/{eid}')
def ver(eid:int,request:Request):
    with obtener_sesion(request.app.state.motor) as s:return detalle(s,acceso(s,request,eid))
@router.post('/{eid}/analizar')
def scan(eid:int,request:Request):
    with obtener_sesion(request.app.state.motor) as s:
        s.connection().exec_driver_sql('BEGIN IMMEDIATE');e=acceso(s,request,eid,True);analizar(s,e);return detalle(s,e)

def fase(s,e,fid):
    f=s.get(Fase,fid)
    if not f or f.expediente_id!=e.id:error('Fase no localizada.',404)
    return f
@router.post('/{eid}/fases/{fid}/accion')
def actuar(eid:int,fid:int,d:Accion,request:Request):
    with obtener_sesion(request.app.state.motor) as s:
        s.connection().exec_driver_sql('BEGIN IMMEDIATE');e=acceso(s,request,eid,True);f=fase(s,e,fid);a=actor(request)
        if d.revision!=f.revision:error('La fase cambió; actualiza la pantalla.')
        if not d.justificacion.strip():error('Justificación requerida.',422)
        req=lista(s,Requisito,fase_id=f.id);obs=lista(s,Observacion,fase_id=f.id);evs=lista(s,Evento,fase_id=f.id)
        q=next((x for x in req if x.id==d.requisito_id),None);o=next((x for x in obs if x.id==d.observacion_id),None);doc=s.get(DocumentoTZ,d.documento_id) if d.documento_id else None
        if doc and doc.fase_id!=f.id:error('Documento ajeno.',422)
        if f.estado=='cerrada' and d.accion!='reabrir':error('Reabre la fase antes de modificarla.')
        old=f.estado; payload={'justificacion':d.justificacion,'estado_anterior':old,'requisito_id':d.requisito_id,'documento_id':d.documento_id,'observacion_id':d.observacion_id}
        if d.accion=='iniciar':
            if old not in ('pendiente','reabierta'):error('Transición inválida.')
            if any(x.orden<f.orden and x.estado!='cerrada' for x in lista(s,Fase,expediente_id=e.id)):error('Cierra las fases anteriores.')
            f.estado='en_ejecucion'
        elif d.accion=='verificar':
            if old not in ('en_ejecucion','observada','en_revision','en_subsanacion'):error('Inicia la fase primero.')
            if not q or not doc or doc.requisito_id!=q.id or doc.version!=max(x.version for x in lista(s,DocumentoTZ,requisito_id=q.id)):error('Selecciona la última versión del documento del requisito.')
            if any(x.estado!='cerrada' and (x.requisito_id is None or x.requisito_id==q.id) for x in obs):error('Resuelve las observaciones antes de validar.')
            q.estado='validado';doc.estado='validado';f.estado='en_revision'
        elif d.accion=='observar':
            if old=='pendiente':error('Inicia la fase primero.')
            if not d.responsable or not d.limite:error('Indica responsable y plazo.',422)
            o=Observacion(fase_id=f.id,requisito_id=q.id if q else None,documento_id=doc.id if doc else None,descripcion=d.justificacion,autor=a,responsable=d.responsable,limite=d.limite.isoformat(),severidad=d.severidad,estado='pendiente',respuestas=[]);s.add(o);s.flush();payload['observacion_id']=o.id;f.estado='observada'
            if q:q.estado='observado'
        elif d.accion in ('subsanar','cerrar_observacion'):
            if not o:error('Selecciona una observación.',422)
            if d.accion=='subsanar' and o.estado in ('pendiente','respondida'):
                o.estado='respondida';f.estado='en_subsanacion'
            elif d.accion=='cerrar_observacion' and o.estado=='respondida':o.estado='cerrada';f.estado='en_revision'
            else:error('Transición de observación inválida.')
            o.respuestas=[*o.respuestas,{'actor':a,'fecha':ahora(),'accion':d.accion,'texto':d.justificacion,'documento_id':d.documento_id}]
        elif d.accion=='visto_bueno':
            if old!='en_revision' or any(x.estado!='validado' for x in req if x.obligatorio) or any(x.estado!='cerrada' for x in obs):error('Faltan requisitos validados u observaciones por cerrar.')
            f.estado='validada'
        elif d.accion=='pago':
            if f.orden!=7 or old!='validada':error('El pago requiere fase de pago validada.')
            if d.monto_autorizado is None or d.monto_pagado is None or not d.monto_autorizado.is_finite() or not d.monto_pagado.is_finite() or d.monto_pagado<0 or d.monto_autorizado<0:error('Montos válidos requeridos.',422)
            if any(x.accion=='pago' for x in evs):error('Ya existe un pago en esta fase.')
            cnf=next(x for x in lista(s,Fase,expediente_id=e.id) if x.orden==6)
            if cnf.estado!='cerrada' or any(x.estado!='cerrada' for x in lista(s,Observacion,fase_id=cnf.id)):error('Conformidad pendiente.')
            payload.update(autorizado=str(d.monto_autorizado),pagado=str(d.monto_pagado),observaciones_conformidad=[])
        elif d.accion=='cerrar':
            if old!='validada':error('Se requiere visto bueno.')
            if f.orden==7 and not any(x.accion=='pago' for x in evs):error('Registra el pago o contraprestación.')
            f.estado='cerrada'
        elif d.accion=='reabrir':
            if old not in ('cerrada','validada'):error('Solo se reabre una fase validada o cerrada.')
            f.estado='reabierta'
        elif d.accion=='asignar':
            if not d.responsable:error('Indica responsable.',422)
            f.responsable=d.responsable
            if d.limite:f.limite=d.limite.isoformat()
        else:error('Acción desconocida.',422)
        f.revision+=1;payload['estado_posterior']=f.estado
        # El responsable de la actuación es siempre la cuenta autenticada; solo 'asignar' registra a otra persona.
        evento(s,e,f,a,d.accion,payload,d.responsable if d.accion=='asignar' else nombre(request));s.flush();analizar(s,e);return detalle(s,e)

@router.post('/{eid}/fases/{fid}/documentos')
def cargar(eid:int,fid:int,request:Request,requisito_id:int=Form(...),autor:str=Form(...),archivo:UploadFile=File(...)):
    data=archivo.file.read(MAX_BYTES+1)
    try:mime,digest=validar_archivo(archivo.filename,archivo.content_type,data)
    except ValueError as ex:error(str(ex),422)
    with obtener_sesion(request.app.state.motor) as s:
        s.connection().exec_driver_sql('BEGIN IMMEDIATE');e=acceso(s,request,eid,True);f=fase(s,e,fid);q=s.get(Requisito,requisito_id)
        if not q or q.fase_id!=f.id:error('Requisito ajeno.',422)
        if f.estado not in ('en_ejecucion','en_revision','observada','en_subsanacion','reabierta'):error('Inicia o reabre la fase.')
        versions=lista(s,DocumentoTZ,requisito_id=q.id);v=max((x.version for x in versions),default=0)+1
        doc=DocumentoTZ(fase_id=f.id,requisito_id=q.id,nombre=archivo.filename,version=v,sha256=digest,contenido=data,mime=mime,autor=autor,registrado_por=actor(request),fecha=ahora(),estado='presentado');s.add(doc);s.flush();q.estado='presentado';f.revision+=1;evento(s,e,f,actor(request),'cargar_documento',{'documento_id':doc.id,'version':v,'sha256':digest,'requisito_id':q.id,'autor_documento':autor},nombre(request));analizar(s,e);return detalle(s,e)
@router.get('/{eid}/documentos/{did}')
def descargar(eid:int,did:int,request:Request):
    with obtener_sesion(request.app.state.motor) as s:
        e=acceso(s,request,eid);d=s.get(DocumentoTZ,did)
        if not d:error('Documento no localizado.',404)
        fase(s,e,d.fase_id)
        return Response(d.contenido,media_type='application/octet-stream',headers={'Content-Disposition':f'attachment; filename="documento-{d.id}-v{d.version}{Path(d.nombre).suffix}"'})
@router.post('/{eid}/alertas/{aid}/revision')
def revisar_alerta(eid:int,aid:int,d:Accion,request:Request):
    with obtener_sesion(request.app.state.motor) as s:
        s.connection().exec_driver_sql('BEGIN IMMEDIATE');e=acceso(s,request,eid,True);a=s.get(AlertaTZ,aid)
        if not a or a.expediente_id!=e.id:error('Alerta no localizada.',404)
        if d.accion not in ('revisada','descartada'):error('Decisión inválida.',422)
        if len(d.justificacion.strip())<15:error('Explica la decisión con al menos 15 caracteres.',422)
        a.estado=d.accion;evento(s,e,s.get(Fase,a.fase_id),actor(request),'revision_alerta',{'alerta_id':aid,'decision':d.accion,'justificacion':d.justificacion},nombre(request));return detalle(s,e)
@router.get('/{eid}/alertas/{aid}/incidente')
def incidente(eid:int,aid:int,request:Request):
    with obtener_sesion(request.app.state.motor) as s:
        e=acceso(s,request,eid);a=s.get(AlertaTZ,aid)
        if not a or a.expediente_id!=e.id:error('Alerta no localizada.',404)
        d=detalle(s,e);orig=a.evidencia['origen_fase_id'];ids={orig,a.fase_id};fs=[f for f in d['fases'] if f['id'] in ids];return {'alerta':dictrow(a),'fases':fs,'eventos':[v for v in d['eventos'] if v['fase_id'] in ids],'posteriores':[f['nombre'] for f in d['fases'] if f['orden']>min(x['orden'] for x in fs)],'recomendacion':'Revisar documentos y actuaciones; no constituye atribución de responsabilidad.'}

def sembrar_trazabilidad(motor):
    with obtener_sesion(motor) as s:
        s.connection().exec_driver_sql('BEGIN IMMEDIATE')
        if s.scalar(select(func.count()).select_from(Expediente)):return
        for malo in (True,False):
            e=crear(s,dict(nombre='Servicio de mantenimiento · '+('caso observado' if malo else 'caso correcto'),objeto='Mantenimiento preventivo de equipos universitarios (simulación)',tipo='servicios',area='Servicios generales',responsable='Mariana Ríos Valverde (demo)',inicio=date.today().isoformat(),monto='12000.00',datos={'sintetico':True}), 'demo')
            for f in lista(s,Fase,expediente_id=e.id):
                f.responsable=['Mariana Ríos Valverde','Diego Salazar Paredes','Valeria Chávez Romero','Renato Vega Córdova','Javier Torres Villanueva','Valeria Chávez Romero','Camila Flores Medina','Mariana Ríos Valverde'][f.orden-1]+' (demo)'
                evento(s,e,f,'registro.demo','iniciar',{'sintetico':True},'Diego Salazar Paredes (demo)')
                for q in lista(s,Requisito,fase_id=f.id):
                    b=f'EVIDENCIA SINTÉTICA: {q.nombre}. Caso demostrativo, no es documento oficial.'.encode();doc=DocumentoTZ(fase_id=f.id,requisito_id=q.id,nombre='evidencia-demo.txt',version=1,sha256=sha256(b).hexdigest(),contenido=b,mime='text/plain',autor='Lucía Mendoza Alvarado (demo)',registrado_por='registro.demo',fecha=ahora(),estado='validado');s.add(doc);s.flush();q.estado='validado';evento(s,e,f,'registro.demo','cargar_documento',{'documento_id':doc.id,'version':1},'Diego Salazar Paredes (demo)');evento(s,e,f,'verificador.demo','verificar',{'documento_id':doc.id,'requisito_id':q.id},'Valeria Chávez Romero (demo)')
                if malo and f.orden==6:
                    o=Observacion(fase_id=f.id,descripcion='Servicio incompleto: falta evidencia de inspección.',autor='verificador.demo',responsable='Javier Torres Villanueva (demo)',limite=(date.today()+timedelta(days=4)).isoformat(),severidad='alta',estado='pendiente',respuestas=[]);s.add(o);s.flush();evento(s,e,f,'verificador.demo','observar',{'observacion_id':o.id},'Valeria Chávez Romero (demo)')
                evento(s,e,f,'aprobador.demo','visto_bueno',{'sintetico':True},'Renato Vega Córdova (demo)')
                if f.orden==7:
                    evento(s,e,f,'tesoreria.demo','pago',{'autorizado':'12000.00','pagado':'12000.00','observaciones_conformidad':[o.id] if malo else []},'Camila Flores Medina (demo)')
                f.estado='cerrada';evento(s,e,f,'aprobador.demo','cerrar',{'sintetico':True},'Renato Vega Córdova (demo)')
            analizar(s,e)
