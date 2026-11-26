import json
from pathlib import Path
from sqlalchemy import select,func
from db.trazabilidad import Expediente,Fase,Evento
from db.database import obtener_sesion,crear_motor,crear_tablas
from services.datos_publicos import sembrar_historico
from services.trazabilidad import detalle

def test_integracion_historica(tmp_path):
    base=Path(__file__).resolve().parents[1]/'data/publicos'
    r=json.loads((base/'unt_historico.json').read_text(encoding='utf8'))
    assert len(r)==len({x['id_fuente'] for x in r})==529
    assert sum('analisis_historico' in x for x in r)==430
    m=crear_motor(tmp_path/'historico.sqlite');crear_tablas(m)
    try:
        assert sembrar_historico(m)==530
        assert sembrar_historico(m)==0
        with obtener_sesion(m) as s:
            assert s.scalar(select(func.count()).select_from(Expediente))==530
            assert s.scalar(select(func.count()).select_from(Fase))==4240
            assert s.scalar(select(func.count()).select_from(Evento).where(Evento.accion.in_(['pago','visto_bueno','verificar'])))==0
            e=next(x for x in s.scalars(select(Expediente)) if x.datos['registro_publico'].get('analisis_historico'))
            d=detalle(s,e);assert d['datos']['registro_publico']['fuentes'] and len(d['fases'])==8
            assert all(f['estado']=='pendiente' for f in d['fases'])
    finally:m.dispose()
