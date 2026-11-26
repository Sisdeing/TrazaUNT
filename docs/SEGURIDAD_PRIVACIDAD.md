# Seguridad, privacidad y alcance

El servidor identifica a la persona que registra la decisión mediante una cuenta local o la sesión iniciada por el operador del equipo. Las contraseñas se guardan con scrypt, sal aleatoria de 16 bytes y comparación de tiempo constante. Las sesiones usan tokens aleatorios en memoria, cookie HttpOnly y SameSite=Strict, caducidad de cuatro horas y revocación al cerrar sesión. HTTPS habilita Secure. El servidor limita intentos por origen y exige cabecera de cliente en las escrituras. El frontend se sirve en el mismo origen y el despliegue local escucha en loopback.

| Rol local | Permiso efectivo |
|---|---|
| Analista y administrador | Análisis documental, comparación, revisiones, verificación, abonos, reevaluación y exportación. En esta fase comparten el ámbito de análisis. |
| Consulta | Lectura de expedientes, proveedores y concesiones. Sin escrituras, archivos de propuestas, exportación general ni bitácora de accesos. |
| Auditor | Indicadores agregados del dashboard, inteligencia económica y métricas de reglas. Las listas nominales y alertas individuales se excluyen en el servidor. |

El lanzador crea un código aleatorio de un solo uso que pasa al navegador en el fragmento de la URL. Se intercambia por la cookie y se elimina de la barra de dirección. Sólo es válido durante los tres primeros minutos de ese arranque. El operador que puede ejecutar el programa en el equipo ya controla los archivos locales. La aplicación no publica cuentas ni contraseñas de demostración.

Los archivos privados se guardan en SQLite. La API sirve originales como descargas autenticadas con cabeceras de contenido y caché. Los accesos sensibles y operaciones se registran sin copiar contraseñas ni cuerpos de solicitudes. Los CSV de alertas e historial neutralizan prefijos de fórmulas. La bitácora es modificable por quien administre el archivo SQLite. La protección de disco, las copias y las cuentas del sistema operativo corresponden al operador.

El escenario usa empresas ficticias. El único modo público implementado consulta campos registrales de personas jurídicas en un archivo independiente. No se habilitan búsquedas de personas naturales reales. Los resultados están destinados a revisión académica. La ampliación a información institucional requiere definir legitimación, acceso por expediente, retención, descargo, cifrado y revisión externa.
