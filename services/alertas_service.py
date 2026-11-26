"""Persistencia, revisión transaccional y evaluación separada de decisiones humanas."""
from datetime import timezone
from zoneinfo import ZoneInfo
import json
from sqlalchemy import select
from db.database import obtener_sesion, consultar_contrataciones, consultar_pagos, consultar_ground_truth
from db.models import Alerta, Bitacora
from services.scoring import evaluar_expedientes
from services.configuracion import cargar_configuracion


def sincronizar(motor):
    with obtener_sesion(motor) as s:
        contratos, pagos = consultar_contrataciones(s), consultar_pagos(s)
    config = cargar_configuracion()
    resultados = evaluar_expedientes(contratos, pagos, config)
    with obtener_sesion(motor) as s:
        s.connection().exec_driver_sql('BEGIN IMMEDIATE')
        existentes = {(a.contratacion_id, a.regla_id): a for a in s.scalars(select(Alerta))}
        vigentes = set()
        for r in resultados:
            for h in r['hallazgos']:
                clave = (r['contratacion_id'], h['regla_id']); vigentes.add(clave)
                evidencia = {**h['evidencia_json'], '_vigente': True, '_ia': r['ia'],
                             '_priorizacion': r['priorizacion'], '_configuracion': config}
                a = existentes.get(clave)
                if a is None:
                    a = Alerta(contratacion_id=clave[0], regla_id=clave[1], severidad=h['severidad'],
                               score=r['priorizacion']['score'], evidencia_json=evidencia,
                               explicacion=r['explicacion'], estado='pendiente')
                    s.add(a); s.flush()
                    s.add(Bitacora(alerta_id=a.id, accion='detectada', analista='Sistema', comentario='Regla activada; requiere revisión humana.'))
                elif a.evidencia_json != evidencia or a.explicacion != r['explicacion']:
                    anterior = {'evidencia': a.evidencia_json, 'explicacion': a.explicacion, 'score': float(a.score)}
                    s.add(Bitacora(alerta_id=a.id, accion='reevaluada', analista='Sistema', comentario=json.dumps(anterior, ensure_ascii=False)))
                    a.evidencia_json, a.explicacion = evidencia, r['explicacion']
                    a.score, a.severidad = r['priorizacion']['score'], h['severidad']
        for clave, a in existentes.items():
            if clave not in vigentes and a.evidencia_json.get('_vigente', True):
                a.evidencia_json = {**a.evidencia_json, '_vigente': False}
                s.add(Bitacora(alerta_id=a.id, accion='no_vigente', analista='Sistema', comentario='La regla ya no se activa; se conserva el historial.'))
    return resultados


def revisar(motor, alerta_id, estado, analista, comentario, estado_esperado):
    if type(alerta_id) is not int or estado not in ('confirmada', 'descartada'):
        raise ValueError('Acción de revisión inválida.')
    if not isinstance(analista, str) or not analista.strip() or len(analista) > 150:
        raise ValueError('Indica el nombre del analista (hasta 150 caracteres).')
    if not isinstance(comentario, str) or not comentario.strip() or len(comentario) > 4000:
        raise ValueError('Escribe un comentario de 1 a 4000 caracteres.')
    with obtener_sesion(motor) as s:
        s.connection().exec_driver_sql('BEGIN IMMEDIATE')
        a = s.get(Alerta, alerta_id)
        if a is None or not a.evidencia_json.get('_vigente', True):
            raise ValueError('La alerta ya no está vigente. Actualiza la vista.')
        if a.estado != estado_esperado:
            raise ValueError('Otro cambio modificó esta alerta. Actualiza antes de revisar.')
        if a.estado == estado:
            raise ValueError('La alerta ya tiene ese estado; no se duplica la acción.')
        anterior = a.estado; a.estado = estado
        s.add(Bitacora(alerta_id=a.id, accion=estado, analista=analista.strip(), comentario=f'{anterior} → {estado}: {comentario.strip()}'))


def leer_panel(motor, resultados):
    with obtener_sesion(motor) as s:
        contratos, pagos = consultar_contrataciones(s), consultar_pagos(s)
        alertas = [dict(id=a.id, contratacion_id=a.contratacion_id, regla_id=a.regla_id, severidad=a.severidad,
                        score=float(a.score), evidencia=a.evidencia_json, explicacion=a.explicacion, estado=a.estado,
                        vigente=a.evidencia_json.get('_vigente', True)) for a in s.scalars(select(Alerta).order_by(Alerta.score.desc(), Alerta.id))]
        historial = [dict(id=b.id, alerta_id=b.alerta_id, accion=b.accion, analista=b.analista, comentario=b.comentario,
                          fecha=b.fecha.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('America/Lima')).isoformat())
                     for b in s.scalars(select(Bitacora).order_by(Bitacora.id.desc()))]
        verdad = consultar_ground_truth(s)
    positivos = {r['contratacion_id'] for r in resultados if r['hallazgos']}
    tp = sum(v['es_anomalia_real'] and v['id'] in positivos for v in verdad)
    fp = sum(not v['es_anomalia_real'] and v['id'] in positivos for v in verdad)
    fn = sum(v['es_anomalia_real'] and v['id'] not in positivos for v in verdad)
    tn = len(verdad) - tp - fp - fn
    metricas = dict(tp=tp, fp=fp, fn=fn, tn=tn, precision=tp/(tp+fp) if tp+fp else None,
                    recall=tp/(tp+fn) if tp+fn else None, tasa_fp=fp/(fp+tn) if fp+tn else None)
    # Nunca se envían etiquetas individuales al navegador.
    return json.loads(json.dumps(dict(contratos=contratos, pagos=pagos, alertas=alertas, historial=historial,
                                      resultados=resultados, metricas=metricas), default=str))
