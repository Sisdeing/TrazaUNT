# Migración de TrazaUNT 2.0 a 3.0

Se conservan React 19, Vite 7, FastAPI, SQLAlchemy y SQLite. Las rutas históricas y la navegación hash siguen disponibles. La API exige sesión en los módulos de datos. Los clientes deben autenticar su cuenta, conservar la cookie y enviar X-Traza-Client: react en las escrituras. La identidad de la bitácora se resuelve en el servidor.

El resumen incorpora agregados económicos y de cartera. Convocatorias, propuestas, documentos, calificaciones, integridad, concesiones y predicciones se registran mediante routers nuevos. Los nombres y semánticas de R01–R06 se mantienen para conservar las decisiones anteriores.

La extensión de esquema es aditiva. Respaldar la base antes de actualizar y probar la apertura en una copia. No ejecutar varios procesos contra la misma demo. La última compilación se encuentra en frontend/dist y las pruebas React en frontend/src. La validación realizada y sus limitaciones se encuentran en [VALIDACION.md](docs/calidad/VALIDACION.md).
