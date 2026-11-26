# Validación 3.2

Pruebas nuevas API: 3 aprobadas. Suite completa: 1 failed, 45 passed, 8 subtests passed in 20.44s

El fallo se encuentra en la extracción aislada de RUC del PDF de la cafetería. No se certifica la extracción en este entorno. `node --check` aprobó los scripts disponibles. No se ejecutaron Vite, Vitest ni E2E de navegador por falta de dependencias npm.
