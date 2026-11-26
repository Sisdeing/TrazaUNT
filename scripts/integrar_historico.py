"""Ingesta reproducible de OCDS filtrado y XLSX oficiales. Uso: python scripts/integrar_historico.py [zip_complementario]."""
import csv,gzip,json,sys,re,zipfile,io,collections,unicodedata,math
from datetime import datetime,date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
D=ROOT/'data/publicos'; URL='https://data.open-contracting.org/es/publication/135'; OECE='https://www.gob.pe/es/14272-acceder-al-portal-de-datos-abiertos-del-oece'
def norm(v):return ''.join(c for c in unicodedata.normalize('NFKD',str(v or '')) if not unicodedata.combining(c)).upper()
def dt(v):
 if isinstance(v,(datetime,date)):return v.isoformat()[:10]
 for fmt in ('%Y-%m-%d','%d/%m/%Y'):
  try:return datetime.strptime(str(v)[:10],fmt).date().isoformat()
  except ValueError:pass
 return ''
def num(v):
 try:
  f=float(v);return f if math.isfinite(f) and f>=0 else None
 except (ValueError,TypeError):return None
def cat(v):
 v=norm(v);return 'bienes' if v in ('GOODS','BIEN','BIENES') else 'obras' if v in ('WORKS','OBRA','OBRAS') else 'servicios' if v in ('SERVICES','SERVICIO','SERVICIOS','CONSULTORIA DE OBRA') else 'otros'
def key(v):return str(v or '').strip().removesuffix('.0')
def isunt(v):return 'UNIVERSIDAD NACIONAL DE TRUJILLO' in norm(v)
def src(name,url=OECE,**kw):return dict(titulo=name,url=url,tipo='Registro público',**kw)
def hit(r,phase,activity,d,source=0):
 d=dt(d); h=dict(fase=phase,actividad=activity,fecha=d,fuente=source)
 if d and h not in r['hitos']:r['hitos'].append(h)
def doc(r,phase,title,url):
 if str(url).startswith('https://') and not any(x['url']==url for x in r['fuentes']):r['fuentes'].append(src(title,url,fase=phase))
def empty(id,title,description,category,fecha,amount,source):return dict(id_fuente=id,nombre=title or description,objeto=description or title,tipo=category,inicio=dt(fecha),monto=amount,monto_tipo='Valor referencial publicado (PEN)',proveedores=[],postores=[],comite=[],contratos_publicados=[],fuentes=[source],hitos=[],registros_complementarios=[])
records={}; aliases={}; contract_ids={}; metrics=[]; counts=collections.Counter(); source_stats={}; entities=set()
with gzip.open(D/'universidades_ocds.jsonl.gz','rt',encoding='utf8') as f:
 for line in f:
  x=json.loads(line);r=x['registro'];t=r.get('tender') or {};b=r.get('buyer') or {};a=r.get('awards') or [];cs=r.get('contracts') or [];v=t.get('value') or {};p=t.get('tenderPeriod') or {};start=dt(t.get('datePublished') or p.get('startDate'));end=dt(p.get('endDate'));typ=cat(t.get('mainProcurementCategory'));amount=num(v.get('amount')) if v.get('currency')=='PEN' else None; n=num(t.get('numberOfTenderers'));entities.add(b.get('name'))
  metrics.append(dict(ocid=r['ocid'],entidad=b.get('name'),categoria=typ,fecha=start,monto=amount,postores=n,metodo=t.get('procurementMethodDetails'),unt=isunt(b.get('name'))))
  if not isunt(b.get('name')):continue
  k=key(t.get('id')); id=r['ocid']; rr=empty(id,t.get('title'),t.get('description'),typ,start,amount,src(x['archivo'],URL));rr.update(codigo_convocatoria=k,modalidad=t.get('procurementMethodDetails'),moneda=v.get('currency'),valor_original=v.get('amount'),fecha_registro_ocds=r.get('date'),archivo=x['archivo'],postores=[{'id':q.get('id'),'nombre':q.get('name')} for q in t.get('tenderers',[]) if q.get('name')]);records[id]=rr;aliases[k]=id
  hit(rr,3,'Convocatoria publicada',start);hit(rr,3,'Fecha límite publicada de ofertas (programada)',end)
  for aa in a:
   hit(rr,4,'Fecha de adjudicación publicada',aa.get('date'))
   rr['proveedores']+= [s['name'] for s in aa.get('suppliers',[]) if s.get('name') and aa.get('status') not in ('cancelled','unsuccessful')]
  for c in cs:
   contract_ids[key(c.get('id'))]=id;rr['contratos_publicados'].append({k:c.get(k) for k in ('id','title','status','value','period','dateSigned','implementation')});hit(rr,4,'Firma de contrato publicada',c.get('dateSigned'));hit(rr,5,'Fin contractual previsto (no acredita ejecución)',(c.get('period') or {}).get('endDate'))
  for phase,objs in ((3,[t]),(4,a+cs)):
   for o in objs:
    for d in o.get('documents',[]):doc(rr,phase,d.get('title') or d.get('documentType') or 'Documento publicado',d.get('url'))
  rr['proveedores']=sorted(set(rr['proveedores']));counts['ocds_unt']+=1
if len(sys.argv)>1:
 from xml.etree import ElementTree as ET
 with zipfile.ZipFile(sys.argv[1]) as z:
  files=sorted(n for n in z.namelist() if n.endswith('.xlsx'))
  def rows(n):
   # Lectura de la primera hoja del formato XLSX observado, con cadenas compartidas.
   ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
   with zipfile.ZipFile(io.BytesIO(z.read(n))) as w:
    strings=[]
    with w.open('xl/sharedStrings.xml') as f:
     for _,e in ET.iterparse(f,events=('end',)):
      if e.tag==ns+'si':strings.append(''.join(t.text or '' for t in e.iter(ns+'t')));e.clear()
    # Las hojas originales contienen celdas con valores simples y sin fórmulas.
    data=w.read('xl/worksheets/sheet1.xml'); h={}
    for m in re.finditer(rb'<row\b[^>]*\br="(\d+)"[^>]*>(.*?)</row>',data,re.S):
     i=int(m[1]); row={}
     for c in re.finditer(rb'<c\b([^>]*?)>(.*?)</c>',m[2],re.S):
      col=re.search(rb'\br="([A-Z]+)\d+"',c[1]);v=re.search(rb'<v>(.*?)</v>',c[2],re.S)
      if not col or not v:continue
      col=col[1].decode();value=v[1].decode()
      if b't="s"' in c[1]:value=strings[int(value)]
      else:
       try:value=float(value) if '.' in value else int(value)
       except ValueError:pass
      row[col]=value
     if i==1:h=row;continue
     yield i,{h[k]:v for k,v in row.items() if k in h}
  def addrow(rr,n,i,row,fields):
   rr['registros_complementarios'].append({'archivo':Path(n).name,'fila':i,'datos':{k:row.get(k) for k in fields}})
   if not any(s['titulo']==Path(n).name for s in rr['fuentes']):rr['fuentes'].append(src(Path(n).name))
   return next(j for j,s in enumerate(rr['fuentes']) if s['titulo']==Path(n).name)
  for n in files:
   if not any(w in n for w in ('ADJUDICACIONES','DESIERTOS','CONTRATOS')):continue
   total=used=0
   for i,row in rows(n):
    total+=1
    if not (isunt(row.get('ENTIDAD')) or key(row.get('ENTIDAD_RUC'))=='20172557628' or key(row.get('CODIGOENTIDAD')).lstrip('0')=='1894'):continue
    k=key(row.get('CODIGOCONVOCATORIA'));title=row.get('PROCESO') or row.get('DESCRIPCION_PROCESO');desc=row.get('DESCRIPCION_PROCESO');id=aliases.get(k) or 'SEACE-CONVOCATORIA-'+k
    if not k or not title:continue
    if id not in records:
     records[id]=empty(id,title,desc,cat(row.get('OBJETOCONTRACTUAL')),row.get('FECHA_CONVOCATORIA'),None,src(Path(n).name));records[id]['codigo_convocatoria']=k;aliases[k]=id
    rr=records[id]; used+=1;ss=addrow(rr,n,i,row,tuple(row))
    if rr['tipo']=='otros' and row.get('OBJETOCONTRACTUAL'):rr['tipo']=cat(row['OBJETOCONTRACTUAL'])
    if not rr['inicio']:rr['inicio']=dt(row.get('FECHA_CONVOCATORIA'))
    hit(rr,3,'Convocatoria publicada',row.get('FECHA_CONVOCATORIA'),ss);hit(rr,4,'Buena pro publicada',row.get('FECHA_BUENAPRO'),ss);hit(rr,4,'Consentimiento publicado',row.get('FECHA_CONSENTIMIENTO_BP'),ss)
    if row.get('PROVEEDOR') and row['PROVEEDOR'] not in rr['proveedores']:rr['proveedores'].append(row['PROVEEDOR'])
    if 'DESIERTOS' in n:rr['resultado_items_publicado']='Consultar estados por ítem; no implica que todo el procedimiento sea desierto'
    if 'CONTRATOS' in n:
     cid=key(row.get('CODIGO_CONTRATO') or row.get('N_COD_CONTRATO'));contract_ids[cid]=id;rr['contratos_publicados'].append({'id':cid,'title':row.get('NUM_CONTRATO'),'value':{'amount':num(row.get('MONTO_CONTRATADO_TOTAL')),'currency':row.get('MONEDA')},'dateSigned':dt(row.get('FECHA_SUSCRIPCION_CONTRATO'))});hit(rr,4,'Firma de contrato publicada',row.get('FECHA_SUSCRIPCION_CONTRATO'),ss);doc(rr,4,row.get('NUM_CONTRATO') or 'Contrato publicado',row.get('URLCONTRATO'));hit(rr,5,'Fecha fin prevista publicada',row.get('FECHA_VIGENCIA_FIN_ACTUALIZADA') or row.get('FECHA_VIGENCIA_FINAL'),ss)
   source_stats[Path(n).name]={'filas':total,'vinculadas_unt':used};print(Path(n).name,total,used,flush=True)
  for n in files:
   if 'MIEMBROCOMITE' not in n:continue
   total=used=0
   for i,row in rows(n):
    total+=1; id=aliases.get(key(row.get('CODIGOCONVOCATORIA')))
    if id and row.get('MIEMBROCOMITE'):
     rr=records[id];person=row['MIEMBROCOMITE'];used+=1
     if person not in rr['comite']:rr['comite'].append(person)
     addrow(rr,n,i,row,tuple(row))
   source_stats[Path(n).name]={'filas':total,'vinculadas_unt':used};print(Path(n).name,total,used,flush=True)
  # Registros de proveedores: solo coincidencias exactas de RUC con proveedores publicados.
  ids=set()
  for rr in records.values():
   for q in rr['postores']:ids.add(key(q.get('id')).removeprefix('PE-RUC-'))
   for q in rr['registros_complementarios']:
    for k in ('RUC PROVEEDOR','RUC_CONTRATISTA'):
     if q['datos'].get(k):ids.add(key(q['datos'][k]))
  padron=[]
  for n in files:
   if 'PROVEEDORES' not in n:continue
   total=used=0
   for i,row in rows(n):
    total+=1
    if key(row.get('RUC PROVEEDOR')) in ids:padron.append({'archivo':Path(n).name,'fila':i,'datos':row});used+=1
   source_stats[Path(n).name]={'filas':total,'vinculadas_unt':used};print(Path(n).name,total,used,flush=True)
  (D/'padron_unt.json').write_text(json.dumps(padron,default=str,ensure_ascii=False),encoding='utf8')
  (D/'unt_historico.json').write_text(json.dumps(list(records.values()),default=str,ensure_ascii=False),encoding='utf8')
  (D/'cobertura_complementaria.json').write_text(json.dumps(source_stats,indent=2),encoding='utf8')
  (D/'universidades_variables.json').write_text(json.dumps(metrics,ensure_ascii=False),encoding='utf8')
  # Los asientos CID se vinculan por código exacto de contrato, nunca por nombres aproximados.
  for n in files:
   if 'CID2026' not in n:continue
   total=used=unlinked=0; orphan=[]
   for i,row in rows(n):
    total+=1
    if not (isunt(row.get('ENTIDAD')) or key(row.get('RUC_ENTIDAD'))=='20172557628'):continue
    id=contract_ids.get(key(row.get('CODIGOCONTRATO')))
    if not id:orphan.append({'archivo':Path(n).name,'fila':i,'datos':row});unlinked+=1;continue
    rr=records[id];used+=1;ss=addrow(rr,n,i,row,('CODIGOCONTRATO','NUMEROASIENTO','TITULO','DESCRIPCION','FECHA_PUBLICACION_ASIENTO','ESTADOOBRA','ESTADOCUADERNOOBRA'));hit(rr,5,'Asiento de cuaderno de obra publicado: '+str(row.get('NUMEROASIENTO')),row.get('FECHA_PUBLICACION_ASIENTO'),ss)
   source_stats[Path(n).name]={'filas':total,'vinculadas_unt':used,'unt_sin_vinculo':unlinked};print(Path(n).name,total,used,unlinked,flush=True)
   (D/'cid_unt_sin_vinculo.json').write_text(json.dumps(orphan,default=str,ensure_ascii=False),encoding='utf8')
(D/'unt_historico.json').write_text(json.dumps(list(records.values()),default=str,ensure_ascii=False),encoding='utf8')
(D/'cobertura_complementaria.json').write_text(json.dumps(source_stats,indent=2),encoding='utf8')
(D/'universidades_variables.json').write_text(json.dumps(metrics,ensure_ascii=False),encoding='utf8')
print('Expedientes únicos',len(records),'OCDS UNT',counts['ocds_unt'],'universidades/entidades',len(entities),flush=True)
