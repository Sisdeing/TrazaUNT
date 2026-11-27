import csv
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from fastapi.testclient import TestClient
from app import crear_app
from services.escenario_demo import CONTRATOS as DEMO

# 600 contrataciones sintéticas + el historial de demostración (Horizonte y Aurora).
TOTAL_CONTRATOS = 600 + len(DEMO)
from services.seguridad import guardar_cuenta

HEADERS={'X-Traza-Client':'react'}


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.app=crear_app(Path(cls.tmp.name)/'api.sqlite3')
        cls.context=TestClient(cls.app)
        cls.client=cls.context.__enter__()
        guardar_cuenta(cls.app.state.motor, 'prueba', 'Prueba API', 'analista', 'clave-de-prueba-local')
        cls.client.post('/api/sesion/entrar', headers=HEADERS, json={'usuario':'prueba','clave':'clave-de-prueba-local'}).raise_for_status()
    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None,None,None);cls.tmp.cleanup()
    def test_resumen(self):
        r=self.client.get('/api/resumen');self.assertEqual(r.status_code,200)
        d=r.json();self.assertEqual(d['contrataciones'],TOTAL_CONTRATOS)
        self.assertLessEqual(len(d['prioritarias']),6)
        self.assertNotIn('contratos',d)
    def test_paginacion_filtros_y_privacidad(self):
        a=self.client.get('/api/expedientes?pagina=1&tamano=10').json()
        b=self.client.get('/api/expedientes?pagina=2&tamano=10').json()
        self.assertEqual(a['total'],TOTAL_CONTRATOS);self.assertEqual(len(a['items']),10)
        self.assertTrue(set(x['id'] for x in a['items']).isdisjoint(x['id'] for x in b['items']))
        q=self.client.get('/api/expedientes',params={'q':a['items'][0]['codigo']}).json()
        self.assertEqual(q['total'],1)
        self.assertNotIn('es_anomalia_real',str(q));self.assertNotIn('tipos_anomalia_real',str(q))
        self.assertEqual(self.client.get('/api/expedientes?tamano=101').status_code,422)
        self.assertEqual(self.client.get('/api/expedientes?q=%25').json()['total'],0)
    def test_detalle_y_validacion(self):
        d=self.client.get('/api/expedientes/1').json()
        self.assertIn('explicacion',d);self.assertIn('pagos',d);self.assertEqual(len(d['ia']['variables']),6)
        self.assertNotIn('es_anomalia_real',str(d))
        self.assertEqual(self.client.get('/api/expedientes/999999').status_code,404)
        self.assertEqual(self.client.get('/api/inexistente').status_code,404)
    def test_revision_conflicto_y_reanalisis(self):
        a=self.client.get('/api/alertas').json()['items'][0]
        payload={'estado':'confirmada','estado_esperado':a['estado'],'analista':'Prueba API','comentario':'=Comprobación sintética'}
        url=f"/api/alertas/{a['id']}/revision"
        self.assertEqual(self.client.post(url,json=payload).status_code,403)
        self.assertEqual(self.client.post(url,json={**payload,'analista':'  '},headers=HEADERS).status_code,422)
        self.assertEqual(self.client.post(url,json=payload,headers=HEADERS).status_code,200)
        self.assertEqual(self.client.post(url,json=payload,headers=HEADERS).status_code,409)
        self.assertEqual(self.client.post('/api/analisis',json={},headers=HEADERS).status_code,200)
        detalle=self.client.get(f"/api/expedientes/{a['contratacion_id']}").json()
        self.assertEqual(next(x for x in detalle['alertas'] if x['id']==a['id'])['estado'],'confirmada')
        self.assertTrue(any(x['analista']=='Prueba API' for x in detalle['historial']))
        csv_r=self.client.get('/api/exportar/historial')
        filas=list(csv.DictReader(StringIO(csv_r.text.lstrip('\ufeff'))))
        self.assertTrue(any(x['comentario'].startswith('pendiente') for x in filas if x['analista']=='Prueba API'))
    def test_exportacion_y_estaticos(self):
        r=self.client.get('/api/exportar/alertas')
        self.assertEqual(r.status_code,200);self.assertIn('attachment',r.headers['content-disposition'])
        self.assertNotIn('es_anomalia_real',r.text)
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertIn('type="module"',self.client.get('/').text)
        self.assertEqual(self.client.get('/assets/brand.svg').status_code,200)
    def test_historial_y_metricas(self):
        h=self.client.get('/api/historial?tamano=5').json()
        self.assertLessEqual(len(h['items']),5)
        m=self.client.get('/api/metricas').json()
        self.assertEqual(sum(m[x] for x in ['tp','tn','fp','fn']),TOTAL_CONTRATOS)
    def test_opciones(self):
        c=self.client.get('/api/configuracion').json()
        self.assertEqual(len(c['reglas']),6);self.assertEqual(len(c['entidades']),11)


if __name__=='__main__':unittest.main()
