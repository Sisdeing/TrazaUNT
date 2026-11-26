"""Ingesta conservadora: fuente pública no equivale a validación institucional."""
import gzip
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from sqlalchemy import select, func
from db.database import obtener_sesion
from db.trazabilidad import Expediente, Fase, Requisito
from services.trazabilidad import PLANTILLAS, evento

RUC = '20172557628'
MUESTRA = Path(__file__).resolve().parents[1] / 'data/publicos/unt_muestra.json'

def fecha(value):
    try: return date.fromisoformat(str(value)[:10]).isoformat()
    except (ValueError, TypeError): return ''

def monto(value):
    try:
        v = Decimal(str(value))
        return str(v.quantize(Decimal('.01'))) if v.is_finite() and 0 <= v < 10**12 else ''
    except (InvalidOperation, ValueError, TypeError): return ''

def importar(motor, registros):
    n = 0
    with obtener_sesion(motor) as s:
        s.connection().exec_driver_sql('BEGIN IMMEDIATE')
        conocidos = {e.datos.get('registro_publico', {}).get('id_fuente') for e in s.scalars(select(Expediente))}
        for r in registros:
            if not r.get('id_fuente') or r['id_fuente'] in conocidos or not r.get('objeto'): continue
            if r.get('tipo') not in PLANTILLAS: continue
            i = (s.scalar(select(func.max(Expediente.id))) or 0) + 1
            inicio = fecha(r.get('inicio')); year = inicio[:4] or str(date.today().year)
            e = Expediente(id=i, codigo=f'EXP-UNT-{year}-{i:06d}', nombre=(r.get('objeto') or r['nombre'])[:200], objeto=r['objeto'], tipo=r['tipo'], area='Universidad Nacional de Trujillo', responsable='No consta en la fuente pública', inicio=inicio, monto=monto(r.get('monto')), propietario='publico', plantilla={'version':1,'fases':PLANTILLAS[r['tipo']]}, datos={'origen':'publico','registro_publico':r})
            s.add(e); s.flush(); fs={}
            for j,(pref,nombre,reqs) in enumerate(PLANTILLAS[r['tipo']],1):
                f=Fase(expediente_id=i,codigo=f'{pref}-{year}-{i:06d}-{j:02d}',orden=j,nombre=nombre,estado='pendiente',responsable='No consta en la fuente pública',limite='',revision=0); s.add(f);s.flush();fs[j]=f
                for q in reqs: s.add(Requisito(fase_id=f.id,nombre=q,estado='pendiente',obligatorio=True))
            evento(s,e,None,'importador.publico','importar_registro',{'id_fuente':r['id_fuente'],'origen':'publico'},'No identificado en la fuente')
            for h in sorted(r.get('hitos',[]),key=lambda x:x.get('fecha','')):
                if fecha(h.get('fecha')) and h.get('fase') in fs:
                    evento(s,e,fs[h['fase']],'importador.publico','hecho_publicado',{'origen':'publico','actividad':h['actividad'],'fuente':h.get('fuente',0)},'No identificado en la fuente',fecha(h['fecha']))
            conocidos.add(r['id_fuente']);n+=1
    return n

def sembrar_publicos(motor):
    return importar(motor,json.loads(MUESTRA.read_text(encoding='utf8')))

def desde_ocds(path):
    """JSONL del registro OCP: solo servicios UNT. No reconstruye actuaciones internas."""
    opener=gzip.open if str(path).endswith('.gz') else open
    with opener(path,'rt',encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            row=json.loads(line); r=row.get('compiledRelease',row)
            buyer=r.get('buyer') or {}; bid=str(buyer.get('id','')); name=str(buyer.get('name','')).upper()
            if not (bid.endswith(RUC) or name.strip()=='UNIVERSIDAD NACIONAL DE TRUJILLO'): continue
            t=r.get('tender') or {}; cat=str(t.get('mainProcurementCategory','')).lower()
            if cat not in ('services','servicios'): continue
            ocid=r.get('ocid'); title=t.get('title') or t.get('description')
            if not ocid or not title: continue
            val=t.get('value') or {}; awards=r.get('awards') or []; contracts=r.get('contracts') or []
            docs=[]; hitos=[]; start=fecha((t.get('tenderPeriod') or {}).get('startDate'))
            if start: hitos.append({'fase':3,'actividad':'Inicio de periodo de licitación publicado','fecha':start,'fuente':0})
            proveedores=[]
            for a in awards:
                if a.get('status')=='active':
                    proveedores.extend(x.get('name') for x in a.get('suppliers',[]) if x.get('name'))
                if fecha(a.get('date')): hitos.append({'fase':4,'actividad':'Fecha de adjudicación publicada (estado: '+str(a.get('status','no informado'))+')','fecha':fecha(a['date']),'fuente':0})
            for c in contracts:
                if fecha(c.get('dateSigned')): hitos.append({'fase':4,'actividad':'Fecha de firma publicada','fecha':fecha(c['dateSigned']),'fuente':0})
            for phase,objects in [(3,[t]),(4,awards+contracts)]:
                for obj in objects:
                    for d in obj.get('documents',[]):
                        if str(d.get('url','')).startswith('https://'):docs.append({'fase':phase,'titulo':d.get('title') or d.get('documentType') or 'Documento publicado','url':d['url'],'tipo':'documento OCDS'})
            yield {'id_fuente':ocid,'nombre':title,'objeto':t.get('description') or title,'tipo':'servicios','inicio':start,'monto':monto(val.get('amount')) if val.get('currency')=='PEN' else '', 'monto_tipo':'Valor de licitación publicado (PEN)', 'proveedores':sorted(set(proveedores)), 'fuentes':[{'titulo':'Registro OCDS del OECE (OCP)','url':'https://data.open-contracting.org/es/publication/135','tipo':'dataset oficial republicado'}]+docs,'hitos':hitos,'contratos_publicados':[{'id':c.get('id'),'estado':c.get('status'),'valor':c.get('value')} for c in contracts]}


def sembrar_historico(motor):
    ruta=MUESTRA.with_name('unt_historico.json')
    if not ruta.exists(): return sembrar_publicos(motor)
    registros=json.loads(ruta.read_text(encoding='utf8'))
    # La muestra 2024 y Turnitin ya están en los archivos históricos; no duplicarlos.
    ids={r['id_fuente'] for r in registros};codigos={r.get('codigo_convocatoria') for r in registros}
    for r in json.loads(MUESTRA.read_text(encoding='utf8')):
        if r['id_fuente'] not in ids and r['id_fuente'].split('-')[-1] not in codigos:registros.append(r)
    return importar(motor,registros)
