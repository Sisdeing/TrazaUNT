import gzip,json,glob,unicodedata,sys
from pathlib import Path
base=Path(__file__).resolve().parents[1]/'data/publicos'; base.mkdir(parents=True,exist_ok=True); allr={}; counts={}
if len(sys.argv)!=2:sys.exit('Uso: python scripts/extraer_universidades.py RUTA_CARPETA_OCDS')
def norm(s):return ''.join(c for c in unicodedata.normalize('NFKD',str(s)) if not unicodedata.combining(c)).upper()
for p in sorted(glob.glob(str(Path(sys.argv[1])/'peru_oece_bulk_*.jsonl.gz'))):
 n=u=t=0
 with gzip.open(p,'rb') as f:
  for line in f:
   n+=1
   if b'UNIVERSIDAD' not in line.upper() and b'20172557628' not in line:continue
   r=json.loads(line); r=r.get('compiledRelease',r); b=r.get('buyer') or {}; name=norm(b.get('name',''))
   if not ('UNIVERSIDAD NACIONAL' in name or 'UNIVERSIDAD PUBLICA' in name or '20172557628' in str(b)):continue
   ocid=r.get('ocid')
   if not ocid:continue
   u+=1; t+=int('UNIVERSIDAD NACIONAL DE TRUJILLO' in name or '20172557628' in str(b)); old=allr.get(ocid)
   if old is None or str(r.get('date',''))>=str(old[0].get('date','')):allr[ocid]=(r,Path(p).name)
 counts[Path(p).name]={'lineas':n,'universidades':u,'unt':t};print(p,counts[Path(p).name],flush=True)
with gzip.open(base/'universidades_ocds.jsonl.gz','wt',encoding='utf8') as f:
 for r,src in allr.values():f.write(json.dumps({'archivo':src,'registro':r},ensure_ascii=False,separators=(',',':'))+'\n')
(base/'cobertura_ocds.json').write_text(json.dumps(counts,indent=2),encoding='utf8');print('unique',len(allr),flush=True)
