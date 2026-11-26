# Datos públicos en TrazaUNT 3.3

## Cobertura comprobada

La muestra `data/publicos/unt_muestra.json` contiene tres procedimientos publicados de la UNT, transcritos de fichas de contratación y páginas de resoluciones consultadas el 24/11/2026 (hora de Lima). Cada registro conserva los enlaces y distingue una publicación oficial de su republicación. No representa una descarga masiva del SEACE ni un universo estadístico.

| Procedimiento | Procedencia |
|---|---|
| Mantenimiento eléctrico del local central | Ficha de SEACE republicada por TodoLicitaciones; OCID ocds-dgv273-seacev3-1058270 |
| Software Turnitin | Ficha de SEACE republicada por TodoLicitaciones; OCID ocds-dgv273-seacev3-1157947 |
| Mantenimiento y manejo de residuos | Resoluciones oficiales OECE 7542-2025-TCP-S6 y 01268-2026-TCP-S1; detalles complementarios de una republicación de la primera resolución. |

Los datos se muestran como referencias públicas, no como certificación de autenticidad. Las fuentes originales enlazadas pueden actualizarse; el archivo no incluye los PDF originales ni inventa su contenido. Se diferencia fecha efectiva documentada de fecha de importación. La fecha final contractual publicada no acredita entrega, pago ni cumplimiento. Los controles internos permanecen pendientes de verificación; ningún nombre ficticio se atribuye a un procedimiento real. Los dos casos demostrativos se identifican como ficticios, incluyendo sus responsables, actuaciones y alertas. Los campos desconocidos no se imputan como cero. Los montos publicados se distinguen de los contractuales.

## Importación ampliada

1. Descargar un archivo anual JSONL.gz desde https://data.open-contracting.org/es/publication/135. La publicación declara licencia CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Atribución: OECE, datos OCDS republicados por Open Contracting Partnership.
2. Detener el servidor y respaldar la base local.
3. Ejecutar `python scripts/importar_ocds.py ruta/al/archivo.jsonl.gz` desde la raíz del proyecto usando el entorno Python del programa.
4. Reiniciar y abrir Expedientes y trazabilidad. El importador filtra la entidad compradora por RUC o nombre exacto, y la categoría de servicios; normaliza fechas y montos PEN, conserva enlaces a documentos, proveedores publicados y datos contractuales disponibles. La fuente se identifica por OCID; duplicados por ese mismo identificador se omiten (no actualiza registros previos). La muestra que usa nomenclatura en lugar de OCID requiere conciliación manual si aparece de nuevo en un archivo OCDS.

El importador acepta JSONL o JSONL.gz del registro OCP; no realiza descargas ni consultas automáticas. Su prueba usa una estructura OCDS controlada, no el archivo masivo, pues la descarga se bloqueó por conectividad. Los usuarios autorizados pueden añadir documentos, verificaciones, observaciones y actuaciones locales; estas no equivalen a actuaciones históricas oficiales. Los expedientes de fuente pública pertenecen a la bandeja compartida de la demo, no a una autorización institucional de producción.

## Límites

El módulo de trazabilidad es el primer componente conectado a esta muestra. Contrataciones, modelos, concesiones, alertas históricas y otros componentes conservan sus datos previos. No se ha importado el MEF, Contraloría en bloque, expedientes privados, ni se ha entrenado IA con datos reales. La base anterior tiene restricciones explícitas para evitar tratar proveedores reales como datos de prueba; por seguridad, no se insertan proveedores públicos en el universo sintético de evaluación. Las reglas TZ no deben interpretarse como pronunciamientos legales. Para fuentes adicionales se requiere ETL, mapeo y validación institucional.
