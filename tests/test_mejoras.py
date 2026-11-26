import copy
from datetime import date, timedelta
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import random
import tempfile
from concurrent.futures import ThreadPoolExecutor
import unittest

from services.configuracion import cargar_configuracion
from services.reglas import regla_fraccionamiento, _objeto_normalizado
from services.anomalias import preparar_variables, evaluar_anomalias, VARIABLES
from services.scoring import calcular_score
from services.alertas_service import sincronizar, leer_panel, revisar
from db.database import crear_motor, obtener_sesion
from db.seed import poblar_si_vacia
from sqlalchemy import inspect


def contrato(i, dia, objeto='Compra de laptops', monto='18000'):
    return dict(id=i, codigo=f'EXP-{i}', entidad_id=1, proveedor_id=1,
                fecha=date(2025, 1, 1)+timedelta(days=dia), objeto=objeto,
                monto=Decimal(monto), fecha_constitucion=date(2020,1,1), n_postores=3)


class ReglasTests(unittest.TestCase):
    def setUp(self):
        self.config = cargar_configuracion()

    def test_sinonimos_y_acentos(self):
        objetos=['Adquisición de computadoras portátiles', 'Compra de laptops intel core i7', 'LAPTOPS']
        filas=[contrato(i+1,i, o) for i,o in enumerate(objetos)]
        h=regla_fraccionamiento(filas, [], self.config)
        self.assertEqual(len(h),3)
        self.assertEqual(len(h[0]['evidencia_json']['objetos_originales']),3)
        self.assertEqual(h[0]['evidencia_json']['monto_acumulado'],'54000.00')

    def test_no_mezcla_servicios(self):
        self.assertNotEqual(_objeto_normalizado('Mantenimiento de laptops'), _objeto_normalizado('Compra de laptops'))
        filas=[contrato(1,0),contrato(2,1),contrato(3,2,'Mantenimiento de laptops')]
        self.assertEqual(regla_fraccionamiento(filas,[],self.config),[])

    def test_no_encadenar_vecinos_fuera_ventana(self):
        filas=[contrato(1,0),contrato(2,29),contrato(3,58)]
        self.assertEqual(regla_fraccionamiento(filas,[],self.config),[])

    def test_limite_inclusivo_y_fecha_maxima(self):
        filas=[contrato(1,0),contrato(2,15),contrato(3,30)]
        self.assertEqual(len(regla_fraccionamiento(filas,[],self.config)),3)
        for c in filas: c['fecha']=date.max
        self.assertEqual(len(regla_fraccionamiento(filas,[],self.config)),3)

    def test_ventana_optimizada_equivale_a_oraculo(self):
        rng=random.Random(42)
        for _ in range(100):
            filas=[contrato(i+1,rng.randrange(100),monto=str(rng.randrange(100,49000))) for i in range(35)]
            orden=sorted(filas,key=lambda c:(c['fecha'],c['id']))
            esperado={}
            for inicio,c in enumerate(orden):
                v=[x for x in orden[inicio:] if (x['fecha']-c['fecha']).days<=30]
                total=sum(x['monto'] for x in v)
                if len(v)>=3 and total>=50000:
                    for x in v:
                        esperado.setdefault(x['id'],([t['id'] for t in v],str(total)))
            observado=regla_fraccionamiento(filas,[],self.config)
            self.assertEqual({x['contratacion_id'] for x in observado},set(esperado))
            for h in observado:
                ids,total=esperado[h['contratacion_id']]
                self.assertEqual([x['id'] for x in h['evidencia_json']['contratos']],ids)
                self.assertEqual(Decimal(h['evidencia_json']['monto_acumulado']),Decimal(total))

    def test_entidad_proveedor_aislados(self):
        filas=[contrato(i,0) for i in range(1,4)];filas[2]['entidad_id']=2
        self.assertEqual(regla_fraccionamiento(filas,[],self.config),[])

    def test_features_sin_etiquetas(self):
        filas=[contrato(i,i,monto=str(i*10000)) for i in range(1,25)]
        a=preparar_variables(filas)
        for c in filas: c.update(es_anomalia_real=True,tipos_anomalia_real=['inventada'])
        self.assertTrue(a.equals(preparar_variables(filas)))
        self.assertEqual(list(a.columns),VARIABLES)
        self.assertAlmostEqual(a.iloc[0]['ratio_monto_promedio'],10000/125000)
        senales=evaluar_anomalias(filas,self.config)
        self.assertTrue(all(0<=s['rareza']<=1 for s in senales.values()))

    def test_ia_no_genera_alertas(self):
        p=calcular_score([],dict(disponible=True,rareza=1),self.config)
        self.assertFalse(p['requiere_revision']);self.assertEqual(p['semaforo'],'verde')

    def test_ia_rechaza_postores_invalidos(self):
        c=contrato(1,0);c['n_postores']=0
        with self.assertRaises(ValueError): preparar_variables([c])


class PersistenciaTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.motor=crear_motor(Path(self.tmp.name)/'test.sqlite3')
        poblar_si_vacia(self.motor,n_normales=100)
    def tearDown(self):
        self.motor.dispose();self.tmp.cleanup()
    def test_wal_e_indice(self):
        with self.motor.connect() as c:
            self.assertEqual(c.exec_driver_sql('PRAGMA journal_mode').scalar(),'wal')
            self.assertEqual(c.exec_driver_sql('PRAGMA foreign_keys').scalar(),1)
        self.assertIn('ix_contratacion_entidad_proveedor_fecha',{x['name'] for x in inspect(self.motor).get_indexes('contrataciones')})
    def test_reanalisis_conserva_decision_y_json(self):
        resultados=sincronizar(self.motor);panel=leer_panel(self.motor,resultados)
        a=panel['alertas'][0]
        revisar(self.motor,a['id'],'confirmada','Revisor','Sustento de prueba','pendiente')
        segunda=sincronizar(self.motor);p2=leer_panel(self.motor,segunda)
        self.assertEqual(next(x for x in p2['alertas'] if x['id']==a['id'])['estado'],'confirmada')
        self.assertEqual(len(panel['alertas']),len(p2['alertas']))
        json.dumps(p2,allow_nan=False)
        with self.assertRaises(ValueError): revisar(self.motor,a['id'],'descartada','Otro','Comentario obsoleto','pendiente')
    def test_concurrencia_misma_alerta(self):
        rs=sincronizar(self.motor);a=leer_panel(self.motor,rs)['alertas'][0]
        def accion(nombre):
            try:
                revisar(self.motor,a['id'],'confirmada',nombre,'Verificación concurrente','pendiente');return 'ok'
            except ValueError: return 'conflicto'
        with ThreadPoolExecutor(max_workers=2) as ex:
            resultados=list(ex.map(accion,['A','B']))
        self.assertCountEqual(resultados,['ok','conflicto'])


if __name__=='__main__': unittest.main()
