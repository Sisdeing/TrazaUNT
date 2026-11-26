# Fuentes y procedencia

| Fuente | Modalidad disponible | Datos y cobertura |
|---|---|---|
| Generador de expedientes | Simulada, semilla 42 | Universo histórico creado localmente. Etiquetas de anomalías reservadas a validación agregada. |
| Cafetería y antecedentes | Simulada | Propuestas, evidencias, declaraciones y cobros coherentes con el escenario. Los archivos de origen están en data/demo/cafeteria. |
| Padrón reducido SUNAT | Importación selectiva offline | RUC empresarial validado, razón social, estado, condición y fecha de corte. La consulta ausente devuelve «No evaluado». |
| Sanciones y obligaciones | Registro manual simulado | Referencia de evidencia, analista, corte y caducidad en la ficha de proveedor demo. |
| OECE/OCDS, SIDJI, Poder Judicial, SUNARP, SUNAFIL y RNP | Referencias para expansión | Falta la integración validada de sus datos y condiciones particulares de uso. |

La descarga del padrón corresponde al operador autorizado. La importación lee el archivo descomprimido fila a fila, comprueba los encabezados, detecta separador y codificación y selecciona sólo los RUC indicados. La tabla registra la última fecha de corte disponible por RUC. La consulta posterior es por clave primaria en `data/real/padron.sqlite3`. Si un RUC desaparece de una actualización, una consulta puede devolver la observación antigua con su fecha: debe interpretarse como dato de ese corte.

```powershell
.\.venv\Scripts\python.exe -m services.padron "C:\datos-autorizados\padron.txt" --corte AAAA-MM-DD --ruc RUC_EMPRESARIAL_VALIDO
```

Sustituye la fecha y el RUC por los del corte autorizado. En Fuentes de información, consulta el mismo RUC. El padrón público prescinde de señales, puntuaciones, domicilios detallados o teléfonos. Nunca incluyas este archivo en la distribución de la demo. [Padrón reducido de SUNAT](https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html).

Para futuras cargas OCDS, inspeccionar primero un release o record oficial, licencia, identificadores y cobertura de adjudicación y contrato. Las ausencias de campos se mantienen sin evaluar. [Portal OCDS de OECE](https://www.gob.pe/52005-acceder-al-portal-de-contrataciones-abiertas-de-la-compra-publica-ocds).
