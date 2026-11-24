# Validación de TrazaUNT React 2.0

## Entorno

Linux con Python 3.12 y Node 24.22.1. Dependencias de ejecución de Python instaladas y React compilado con Vite 7.3.8. El árbol de dependencias de Node queda registrado en `frontend/package-lock.json`.

## Comprobaciones

- 19 pruebas de Python: las 12 del motor/persistencia más 7 de API. Cubren paginación sin solapamientos, búsqueda literal, límites de tamaño, privacidad de etiquetas, detalle de expediente, recursos estáticos, validación de formularios, cabecera de escritura, conflictos, conservación de decisiones tras reanálisis, exportaciones, historial y métricas.
- 5 pruebas de componentes React: envío de decisiones con estado esperado, presentación de conflictos conservando el comentario, inicio/Acerca de/menú, consultas de página/filtros al servidor y errores de conexión.
- Compilación de producción de React con `npm run build` completada. No requiere CDN ni claves externas para funcionar.
- Comprobación en navegador del frontend compilado conectado a FastAPI: panel con 600 expedientes, apertura de un detalle, envío de una revisión sintética, aviso de guardado, estado confirmado y registro correspondiente en Trazabilidad. Los indicadores del inicio reflejaron el cambio de 100 a 99 pendientes y de 0 a 1 decisiones.

Las bases y decisiones usadas en las comprobaciones no se incluyen en el ZIP. Una extracción nueva genera su propio conjunto sintético al iniciar.

## Límites

Los lanzadores .bat/.ps1 no se ejecutaron en Windows en este entorno. No se ha realizado una prueba de carga institucional, auditoría de seguridad ni validación de eficacia sobre datos reales. El sistema conserva su alcance académico local sin autenticación. El soporte móvil está implementado mediante CSS adaptable y probado a nivel de componentes del menú; no se verificó visualmente en todos los tamaños de pantalla.

## Reproducir pruebas

```bat
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

```bash
cd frontend
npm ci
npm test
npm run build
```
