"""Ajuste experimental de Isolation Forest con registros oficiales, sin etiquetas de corrupción."""
import json, math, collections
from pathlib import Path
import numpy as np
from sklearn.ensemble import IsolationForest
D=Path(__file__).resolve().parents[1]/'data/publicos'
r=json.loads((D/'universidades_variables.json').read_text());historico=json.loads((D/'unt_historico.json').read_text());byid={x['id_fuente']:x for x in historico}
models={}; results={};
for category in ('bienes','servicios','obras'):
 rows=[x for x in r if x['categoria']==category and x['monto'] is not None and x['postores'] is not None and x['fecha'] and 2020<=int(x['fecha'][:4])<=2024]
 train=[x for x in rows if x['fecha']<'2024-01-01'];test=[x for x in rows if x['fecha']>='2024-01-01']
 if len(train)<50 or not test:continue
 def X(rr):return np.array([[math.log1p(x['monto']),math.log1p(x['postores'])] for x in rr])
 model=IsolationForest(n_estimators=150,contamination=.05,random_state=42,n_jobs=1).fit(X(train));pred=model.predict(X(test)); scores=-model.score_samples(X(train)); models[category]={'entrenamiento':len(train),'evaluacion_temporal':len(test),'senales_2024':int((pred==-1).sum()),'tasa_senales_2024':round(float((pred==-1).mean())*100,2)}
 for x,score,flag in zip(rows,-model.score_samples(X(rows)),model.predict(X(rows))):
  if x['unt'] and x['ocid'] in byid:
   pct=round(float(np.mean(scores<=score))*100,1);results[x['ocid']]={'metodo':'Isolation Forest','percentil_atipicidad':pct,'senal':bool(flag==-1),'monto_pen':x['monto'],'postores_publicados':x['postores'],'conjunto':'evaluación temporal' if x['fecha']>='2024-01-01' else 'entrenamiento','categoria':category}
for x in historico:
 if x['id_fuente'] in results:x['analisis_historico']=results[x['id_fuente']]
(D/'unt_historico.json').write_text(json.dumps(historico,ensure_ascii=False),encoding='utf8')
summary={'universidades':len(set(x['entidad'] for x in r)),'procedimientos_ocds':len(r),'procedimientos_unt':len(historico),'modelos':models,'unt_con_puntuacion':len(results),'unt_senales':sum(x['senal'] for x in results.values()),'variables':['log(1+monto referencial en PEN)','log(1+número de postores publicados)'],'advertencia':'Atipicidad estadística, no probabilidad de corrupción. Sin etiquetas verificadas no se informa accuracy, F1 ni causalidad. Entrenamiento 2020–2023, evaluación temporal 2024. Los registros anteriores son excluidos del entrenamiento.'}
(D/'analisis_historico.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8'); print(json.dumps(summary,ensure_ascii=False,indent=2))
