# Modelo de datos y conservación

```mermaid
erDiagram
  ENTIDADES ||--o{ CONTRATACIONES : solicita
  PROVEEDORES ||--o{ CONTRATACIONES : participa
  CONTRATACIONES ||--o{ ALERTAS : activa
  ALERTAS ||--o{ BITACORA : revisa
  CONVOCATORIAS ||--o{ POSTULACIONES : recibe
  PROVEEDORES ||--o{ POSTULACIONES : presenta
  CONVOCATORIAS ||--o{ DOCUMENTOS : respalda
  POSTULACIONES o|--o{ DOCUMENTOS : adjunta
  POSTULACIONES ||--o{ EVALUACIONES_PROPUESTAS : califica
  CONVOCATORIAS ||--o{ EVENTOS_CONVOCATORIA : registra
  PROVEEDORES ||--o{ EVIDENCIAS_IFP : documenta
  PROVEEDORES ||--o{ EVALUACIONES_IFP : evalua
  VINCULOS_INTEGRIDAD ||--o{ DECLARACIONES_INTEGRIDAD : aclara
  CONVOCATORIAS o|--o| CONCESIONES : origina
  CONCESIONES ||--o{ CUOTAS_CONCESION : exige
  CUOTAS_CONCESION ||--o{ ABONOS_CONCESION : imputa
  CONCESIONES ||--o{ OBLIGACIONES_CONCESION : supervisa
  CONCESIONES ||--o{ PRONOSTICOS_CONCESION : observa
```

La semilla y el arranque crean tablas ausentes y respetan las decisiones ya registradas. Antes de abrir un archivo existente se comprueba que su esquema corresponde a la demo y que sus proveedores tienen identificadores sintéticos. Un RUC reservado de cafetería ocupado por un registro ajeno detiene la carga.

Para actualizar desde 2.0, detén el servidor y respalda la carpeta de datos antes de usar la nueva versión. Las tablas históricas se conservan. Un segundo arranque recupera propuestas, evidencias, decisiones y pagos. El modelo conserva los originales, las versiones de extracción y la bitácora de correcciones. La restauración consiste en volver al respaldo con la aplicación detenida.
