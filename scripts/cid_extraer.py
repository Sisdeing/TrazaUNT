"""Extrae del XLSX del Cuaderno de Obra Digital (CID) las filas de entidades universitarias.

Uso: python scripts/cid_extraer.py RUTA/CID2022_0.xlsx salida/cid2022.json

Lee el XML de la hoja por flujo (sin cargar el libro en memoria), conserva el número de
fila de cada registro y decodifica solo las cadenas necesarias.
"""
import zipfile, re, json, sys, time, html
if len(sys.argv) != 3:
    sys.exit(__doc__)
src, out = sys.argv[1], sys.argv[2]
t0=time.time(); z=zipfile.ZipFile(src)
CH=1<<24
def stream(member, sep):
    with z.open(member) as f:
        buf=b''
        while True:
            b=f.read(CH)
            if not b:
                if buf: yield buf
                return
            buf+=b; parts=buf.split(sep); buf=parts.pop()
            for p in parts: yield p
T=re.compile(rb'<t[^>]*>(.*?)</t>',re.S)
def texto(si): return html.unescape(b''.join(T.findall(si)).decode('utf8','replace'))
# A: índices de cadenas con UNIVERSIDAD
uni={}
for i,si in enumerate(stream('xl/sharedStrings.xml', b'</si>')):
    if b'UNIVERSIDAD' in si.upper():
        uni[i]=texto(si)
print('A', len(uni), 'cadenas', round(time.time()-t0), 's', flush=True)
C=re.compile(rb'<c r="([A-Z]+)(\d+)"([^>]*?)(?:/>|>(.*?)</c>)',re.S)
V=re.compile(rb'<v>(.*?)</v>',re.S)
filas=[]; n=0; hdr=None
for row in stream('xl/worksheets/sheet1.xml', b'</row>'):
    n+=1
    if hdr is None or b'r="L' in row:
        m=re.search(rb'<c r="L\d+"[^>]*t="s"[^>]*><v>(\d+)</v>',row)
        if hdr is None or (m and int(m.group(1)) in uni):
            cel={}
            for col,_,attrs,inner in C.findall(row):
                v=V.search(inner or b'')
                cel[col.decode()]=(b't="s"' in attrs, v.group(1).decode() if v else (texto(inner) if inner and b'inlineStr' in attrs else None))
            fr=re.search(rb'<row r="(\d+)"',row)
            if hdr is None: hdr=cel
            else: cel['__fila']=(False,int(fr.group(1)) if fr else None); filas.append(cel)
print('B', n, 'filas', len(filas), 'de universidades', round(time.time()-t0), 's', flush=True)
need={int(v) for f in filas+[hdr] for k,(s,v) in f.items() if s and v and k!='__fila'}
strs={}
for i,si in enumerate(stream('xl/sharedStrings.xml', b'</si>')):
    if i in need: strs[i]=texto(si)
def val(c): s,v=c; return strs.get(int(v)) if s and v is not None else v
cols=sorted(hdr, key=lambda c:(len(c),c)); nombres=[val(hdr[c]) for c in cols]
regs=[dict({nombres[k]:(val(f[c])[:1500] if isinstance(val(f[c]),str) else val(f[c])) for k,c in enumerate(cols) if c in f}, _fila=f['__fila'][1]) for f in filas]
json.dump(dict(archivo=__import__('os').path.basename(src), filas_totales=n-1, columnas=nombres, registros=regs), open(out,'w'), ensure_ascii=False)
print('C listo', round(time.time()-t0),'s', flush=True)
