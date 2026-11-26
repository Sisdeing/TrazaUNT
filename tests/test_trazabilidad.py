from datetime import date
from fastapi.testclient import TestClient
from app import crear_app
from services.seguridad import guardar_cuenta
import pytest
H={'X-Traza-Client':'react'}
@pytest.fixture(scope='module')
def client(tmp_path_factory):
    app=crear_app(tmp_path_factory.mktemp('tz')/'test.sqlite')
    with TestClient(app) as c:
        guardar_cuenta(app.state.motor,'tz','Analista TZ','analista','clave-local-prueba-123')
        c.post('/api/sesion/entrar',headers=H,json={'usuario':'tz','clave':'clave-local-prueba-123'}).raise_for_status()
        yield c

def test_demo_y_deduplicacion(client):
    items=[x for x in client.get('/api/trazabilidad').json()['items'] if x['datos'].get('sintetico')];assert len(items)==2
    malo=client.get('/api/trazabilidad/'+str(items[0]['id'])).json()
    bueno=client.get('/api/trazabilidad/'+str(items[1]['id'])).json()
    assert not bueno['alertas'];assert {a['regla'] for a in malo['alertas']}=={'TZ04','TZ05'}
    a=next(a for a in malo['alertas'] if a['regla']=='TZ04');path=f"/api/trazabilidad/{malo['id']}"
    inc=client.get(path+f"/alertas/{a['id']}/incidente").json();assert {f['orden'] for f in inc['fases']}=={6,7}
    assert any(e['accion']=='pago' and e['actor']=='tesoreria.demo' for e in inc['eventos'])
    assert len(client.post(path+'/analizar',headers=H).json()['alertas'])==2
    assert client.get('/trazabilidad').status_code==200

def test_flujo(client):
    payload=dict(nombre='Nuevo',objeto='Servicio',tipo='servicios',area='Área',responsable='Persona',inicio=date.today().isoformat(),monto='200.00')
    r=client.post('/api/trazabilidad',headers=H,json=payload);r.raise_for_status();e=r.json();path=f"/api/trazabilidad/{e['id']}"
    assert client.post('/api/trazabilidad',headers=H,json=payload).json()['codigo']!=e['codigo']
    d=client.get(path).json();assert len({f['codigo'] for f in d['fases']})==8
    f=d['fases'][0];url=path+f"/fases/{f['id']}";q=f['requisitos'][0]
    def action(accion,rev,**kw):return client.post(url+'/accion',headers=H,json=dict(accion=accion,revision=rev,justificacion='Evidencia de prueba',**kw))
    assert action('visto_bueno',0).status_code==409
    assert action('iniciar',0).status_code==200;assert action('iniciar',0).status_code==409
    for i in range(2):
        r=client.post(url+'/documentos',headers=H,data={'requisito_id':q['id'],'autor':'Autor'},files={'archivo':('evidencia.txt',f'v{i}'.encode(),'text/plain')});r.raise_for_status()
    f=r.json()['fases'][0];assert len(f['documentos'])==2
    assert action('verificar',f['revision'],requisito_id=q['id'],documento_id=f['documentos'][0]['id']).status_code==409
    r=action('verificar',f['revision'],requisito_id=q['id'],documento_id=f['documentos'][1]['id']);r.raise_for_status();f=r.json()['fases'][0]
    r=action('observar',f['revision'],requisito_id=q['id'],responsable='Supervisor',limite=date.today().isoformat());r.raise_for_status();f=r.json()['fases'][0];o=f['observaciones'][0]
    for a in ('subsanar','cerrar_observacion'):
        r=action(a,f['revision'],observacion_id=o['id']);r.raise_for_status();f=r.json()['fases'][0]
    assert f['observaciones'][0]['estado']=='cerrada';assert len(f['observaciones'][0]['respuestas'])==2
    assert action('visto_bueno',f['revision']).status_code==409
    for q in f['requisitos']:
        r=client.post(url+'/documentos',headers=H,data={'requisito_id':q['id'],'autor':'Autor'},files={'archivo':('evidencia.txt',b'evidencia final','text/plain')});r.raise_for_status();f=r.json()['fases'][0];doc=[d for d in f['documentos'] if d['requisito_id']==q['id']][-1]
        r=action('verificar',f['revision'],requisito_id=q['id'],documento_id=doc['id']);r.raise_for_status();f=r.json()['fases'][0]
    r=action('visto_bueno',f['revision']);r.raise_for_status();f=r.json()['fases'][0]
    r=action('cerrar',f['revision']);r.raise_for_status();assert r.json()['fases'][0]['estado']=='cerrada'
    assert all(x['actor']=='tz' for x in r.json()['eventos'])
    assert client.get(path+f"/documentos/{doc['id']}").content==b'evidencia final'

def test_anonimo(client):
    cookies=dict(client.cookies);client.cookies.clear();assert client.get('/api/trazabilidad').status_code==401;client.cookies.update(cookies)


def test_fuentes_publicas(client):
    items=client.get('/api/trazabilidad').json()['items']; publicos=[x for x in items if x['datos'].get('origen')=='publico'];assert len(publicos)==3
    for item in publicos:
        path=f"/api/trazabilidad/{item['id']}"
        e=client.get(path).json();assert e['datos']['registro_publico']['fuentes']
        assert all(f['limite']=='' for f in e['fases'])
        assert not any(v['accion'] in ('pago','visto_bueno','verificar') for v in e['eventos'])
        assert not client.post(path+'/analizar',headers=H).json()['alertas']
    from services.datos_publicos import sembrar_publicos
    assert sembrar_publicos(client.app.state.motor)==0


def test_importador_ocds(client, tmp_path):
    import json,gzip
    from services.datos_publicos import importar, desde_ocds
    r={'ocid':'ocds-prueba-controlada','buyer':{'id':'PE-RUC-20172557628'},'tender':{'title':'Registro de prueba','mainProcurementCategory':'services','value':{'amount':100,'currency':'PEN'},'tenderPeriod':{'startDate':'2025-01-01'}},'awards':[],'contracts':[]}
    p=tmp_path/'prueba.jsonl.gz'
    with gzip.open(p,'wt',encoding='utf8') as f:
        f.write(json.dumps(r)+'\n');f.write(json.dumps({**r,'ocid':'otro','buyer':{'id':'otra-entidad'}})+'\n')
    rows=list(desde_ocds(p));assert len(rows)==1;assert rows[0]['monto']=='100.00'
    assert importar(client.app.state.motor,rows)==1
    assert importar(client.app.state.motor,rows)==0
