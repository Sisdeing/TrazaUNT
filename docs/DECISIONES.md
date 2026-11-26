# Decisiones de producto

## Inicio operativo y consulta pública

Mi bandeja reutiliza avisos con evidencia y acceso al expediente. Auditoría conserva el panel agregado. El portal público solo recibe recuentos y montos agregados, incluidos estados de convocatorias y alertas vigentes atendidas. La descarga conserva el origen sintético.

## Entorno y funciones experimentales

TRAZA_ENTORNO admite demo y produccion. El segundo desactiva el acceso automático y el aviso de entorno en el espacio interno. La base de esta distribución sigue siendo sintética. La opción no habilita un despliegue institucional con datos reales.

FUNCIONES_EXPERIMENTALES=1 habilita la vista de pronóstico para administración. La opción habilita también el cálculo, la API con sus permisos actuales y los avisos predictivos. Con la opción apagada se conservan los registros previos en la base.

## Alcance pendiente

El primer incremento de P0 reutiliza los flujos existentes. Quedan pendientes R07 y R10, asignación personal, filtros persistentes, el sistema de componentes completo, Cinzel y el logo configurable, los gráficos y el tiempo de resolución en el portal, el ingreso dividido, la auditoría AA y la reorganización completa de la documentación. P1 y P2 continúan abiertos.

# Decisiones de implementación

| Prioridad | Decisión | Razón y efecto verificable |
|---|---|---|
| P0 | Registrar una línea base local | La carpeta recibida carecía de directorio Git. Se preservó el código de la versión 2 y se verificaron sus 19 pruebas Python y 5 de React antes de la integración. |
| P0 | Conservar los 600 expedientes y agregar perfiles específicos | Reescribir proveedores históricos habría cambiado la población de prueba de R01–R06. Una tabla adicional identifica 60 perfiles con evidencia para IFP. |
| P0 | Guardar originales como BLOB con lectura diferida | La transacción relaciona documento y propietario sin rutas aportadas por usuarios. La distribución estática incluye únicamente la compilación y recursos públicos. |
| P0 | Exigir versión esperada y conservar la evaluación humana | La API serializa escrituras SQLite. Un cambio obsoleto recibe HTTP 409. La identidad de la sesión respalda las decisiones. |
| P0 | Mantener un corte de demostración fijo | Permite repetir la mora y los vencimientos de la cafetería. La auditoría de las operaciones nuevas utiliza la hora real. |
| P1 | Separar índice de riesgo, fiabilidad y predicción | Cada uno tiene un objetivo, variables y horizonte distintos. Un pronóstico individual sólo se publica como categoría experimental. |
| P1 | Separar por archivo SQLite la información pública | El padrón empresarial no recibe señales adversas sintéticas. El usuario decide qué RUC autorizados importar. |
| P2 | Posponer OCR ampliado, interoperabilidad y gestión institucional de identidad | Requieren validación de corpus, acuerdos de acceso y revisión independiente. El inventario de pendientes está en producto/ROADMAP.md. |
