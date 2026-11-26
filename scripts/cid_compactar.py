"""Compacta las extracciones CID en data/publicos/cid_universidades.json.gz.

Uso: python scripts/cid_compactar.py CARPETA_CON_cid2022.json_cid2025.json_cid2026.json [SALIDA]
"""
import json, gzip, collections, datetime, os, sys
from pathlib import Path
if len(sys.argv) not in (2, 3):
    sys.exit(__doc__)
ENTRADA = Path(sys.argv[1])
SALIDA = Path(sys.argv[2]) if len(sys.argv) == 3 else Path(__file__).resolve().parents[1] / "data/publicos/cid_universidades.json.gz"
def iso(v):
    if not v: return ''
    s=str(v).strip()
    for fmt in ('%d/%m/%Y','%Y-%m-%d','%d/%m/%Y %H:%M:%S'):
        try: return datetime.datetime.strptime(s[:19] if ' ' in s else s[:10],fmt).date().isoformat()
        except ValueError: pass
    return s[:10]
def num(v):
    try: return round(float(v),2)
    except (TypeError,ValueError): return None
archivos=[]; contratos={}; asientos=collections.defaultdict(dict)
UNT='20172557628'
for y,nombre in [('2022','CID2022_0.xlsx'),('2025','CID2025_0.xlsx'),('2026','CID2026_0.xlsx')]:
    d=json.load(open(ENTRADA/f'cid{y}.json',encoding='utf8')); regs=d['registros']
    archivos.append(dict(archivo=nombre, carpeta='DATA' if y!='2026' else 'DATA/ñlm', filas=d['filas_totales'], filas_universidades=len(regs),
        contratos_universidades=len({r.get('CODIGOCONTRATO') for r in regs}),
        contratos_unt=len({r.get('CODIGOCONTRATO') for r in regs if str(r.get('RUC_ENTIDAD'))==UNT})))
    for r in regs:
        k=str(r.get('CODIGOCONTRATO'))
        natural='natural' in str(r.get('TIPOPROVEEDOR','')).lower()
        c=contratos.setdefault(k, dict(codigo_contrato=k, entidad=r.get('ENTIDAD'), ruc_entidad=str(r.get('RUC_ENTIDAD') or ''),
            objeto=r.get('DESCRIPCION_OBJETO'), numero_contrato=(r.get('NUM_CONTRATO') or '').strip(), monto=num(r.get('MONTO_CONTRATADO_TOTAL')),
            consorcio=r.get('ES_CONSORCIO'), contratista_ruc='Dato protegido' if natural else str(r.get('RUC_CONTRATISTA') or ''),
            contratista='Persona natural (dato protegido)' if natural else r.get('NOMBRE_CONTRATISTA'), tipo_proveedor=r.get('TIPOPROVEEDOR'),
            fecha_suscripcion=iso(r.get('FECHA_SUSCRIPCION_CONTRATO')), vigencia_inicial=iso(r.get('FECHA_VIGENCIA_INICIAL')),
            vigencia_final=iso(r.get('FECHA_VIGENCIA_FIN_ACTUALIZADA') or r.get('FECHA_VIGENCIA_FINAL')),
            estado_obra=r.get('ESTADOOBRA'), estado_cuaderno=r.get('ESTADOCUADERNOOBRA'), condicion_cuaderno=r.get('CONDICIONCUADERNO'),
            ubicacion=' / '.join(str(x) for x in (r.get('DEPARTAMENTO_OBRA'),r.get('PROVINCIA_OBRA'),r.get('DISTRITO_OBRA')) if x),
            norma=r.get('NORMA_APLICABLE'), asientos=0, primer_asiento='', ultimo_asiento='', fuentes={}))
        f=c['fuentes'].setdefault(nombre, dict(archivo=nombre, hoja='Sheet1', filas=[]))
        f['filas'].append(r['_fila'])
        n=r.get('NUMEROASIENTO'); fecha=iso(r.get('FECHA_PUBLICACION_ASIENTO'))
        key=str(n)
        if key not in asientos[k]:
            asientos[k][key]=dict(numero=n, fecha=fecha, titulo=(r.get('TITULO') or '')[:200], descripcion=(r.get('DESCRIPCION') or '')[:900], archivo=nombre, hoja='Sheet1', fila=r['_fila'])
for k,c in contratos.items():
    a=sorted(asientos[k].values(), key=lambda x:(x['fecha'], int(x['numero']) if str(x['numero']).isdigit() else 0))
    c['asientos']=len(a); c['primer_asiento']=a[0]['fecha'] if a else ''; c['ultimo_asiento']=a[-1]['fecha'] if a else ''
    c['fuentes']=[dict(archivo=v['archivo'],hoja=v['hoja'],filas=len(v['filas']),fila_min=min(v['filas']),fila_max=max(v['filas'])) for v in c['fuentes'].values()]
salida=dict(conjunto='Cuaderno de Obra Digital (CID) — datos abiertos del OECE', generado=datetime.date.today().isoformat(),
    metodo='Lectura por flujo del XLSX; se conservan filas cuya ENTIDAD contiene "UNIVERSIDAD". Vinculación con expedientes solo por CODIGOCONTRATO exacto. Contratistas persona natural ocultos.',
    archivos=archivos, contratos=sorted(contratos.values(), key=lambda c:(c['entidad'] or '', c['codigo_contrato'])),
    asientos_unt={k:sorted(asientos[k].values(), key=lambda x:(x['fecha'], int(x['numero']) if str(x['numero']).isdigit() else 0)) for k,c in contratos.items() if c['ruc_entidad']==UNT})
with gzip.open(SALIDA,'wt',encoding='utf8') as fh: json.dump(salida, fh, ensure_ascii=False)
print(len(contratos),'contratos', sum(len(v) for v in salida['asientos_unt'].values()),'asientos UNT', json.dumps(archivos))
print(collections.Counter(c['tipo_proveedor'] for c in contratos.values()))
