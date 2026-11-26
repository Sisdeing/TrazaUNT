# Cuaderno de Obra Digital (CID) — integración con procedencia

## Archivos de origen

| Archivo | Carpeta entregada | Filas | Filas de universidades | Contratos de universidades | Contratos UNT |
|---|---|---|---|---|---|
| CID2022_0.xlsx | DATA | 908 386 | 23 202 | 66 | 1 |
| CID2025_0.xlsx | DATA | 612 880 | 5 091 | 51 | 0 |
| CID2026_0.xlsx | DATA/ñlm | 95 216 | 86 | 7 | 0 |

Cada fila del CID es un asiento del cuaderno de obra (contrato, entidad, contratista, fechas, estado de la obra y texto del asiento).

## Proceso reproducible

1. `python scripts/cid_extraer.py RUTA/CID2022_0.xlsx cid2022.json` (y lo mismo para 2025 y 2026). Lee el XLSX por flujo, sin cargarlo completo en memoria, y conserva solo las filas cuya ENTIDAD contiene «UNIVERSIDAD», con su número de fila.
2. `python scripts/cid_compactar.py` (en la carpeta de los JSON) genera `data/publicos/cid_universidades.json.gz`: un resumen por contrato y los asientos completos de la UNT.
3. Al iniciar en modo demo, `services/cid.integrar_cid` agrega cada asiento como actuación de la fase **Ejecución contractual** del expediente cuyo contrato publicado tiene el mismo `CODIGOCONTRATO`. La operación es idempotente.

## Reglas

- La vinculación se hace solo por código de contrato exacto, nunca por nombres ni montos aproximados.
- Cada asiento conserva **archivo, hoja y fila**, y su fecha de publicación como fecha efectiva.
- Los contratistas persona natural se muestran como «dato protegido».
- El portal público muestra el número de asientos, las fechas y la fuente, pero no el texto de los asientos, que puede contener nombres de profesionales.

## Resultado

La obra UNT *Construcción de sala de práctica y/o simulación de la Escuela de Derecho* (contrato 2143235, AS-SM-2-2022-UNT/CS-1) queda con 130 asientos entre el 13/10/2022 y el 21/04/2023. La vigencia publicada termina el 27/01/2023; la diferencia se muestra como dato, sin calificarla como irregularidad.
