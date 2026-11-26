# Verificación de cortes de auditoría

Desde la raíz del proyecto, con la aplicación inicializada al menos una vez:

```powershell
python -m scripts.sellar_auditoria sellar data/trazaunt.sqlite3 sello.json
python -m scripts.sellar_auditoria verificar data/trazaunt.sqlite3 sello.json
```

Usa la ruta de la base activa si ejecutaste otra instancia. Entrega el JSON a una persona o sistema con custodia independiente y conserva la fecha y la procedencia por separado. El sello contiene huellas, recuentos e identificadores de corte, sin las filas originales. La lectura usa una sola transacción SQLite y permite que la aplicación siga operando.

El verificador compara las revisiones de alertas, la auditoría de API y los eventos de convocatorias hasta los últimos identificadores sellados. Las nuevas filas con identificadores superiores quedan fuera de ese corte. Códigos de salida: 0 coincide, 1 hay discrepancias y 2 ocurrió un error. Emite otro sello para cubrir operaciones posteriores.

Un sello externo permite detectar cambios posteriores al corte si se conserva una copia auténtica. La herramienta carece de firma, fecha confiable y anclaje automático. Un sello generado después de una alteración puede incorporar esa alteración. Conserva la versión del verificador junto con el sello porque un cambio de esquema puede impedir comparar cortes antiguos.
