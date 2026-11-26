# Validación de TrazaUNT 3.0

**24 de noviembre de 2026 · Windows x64.** Se ejecutaron la API, el frontend compilado y el caso de cafetería sobre bases temporales independientes. La entrega incluye una base inicial limpia.

| Comprobación | Resultado observado |
|---|---|
| Línea base de la versión 2 | 19 pruebas Python y 5 de React aprobadas con dependencias instaladas. Compilación Vite reproducida. |
| Python 3.14 · unittest | **41 pruebas aprobadas**. Incluyen las 19 originales con autenticación en la preparación de la suite de API. |
| React · Vitest 4.1.12 | **11 pruebas aprobadas** en dos archivos. Se conservaron las cinco comprobaciones originales adaptadas a la sesión y al panel nuevo. |
| React 19 · Vite 7.3.8 | Compilación de producción completada. Recursos estáticos y fuentes empaquetados en frontend/dist. |
| E2E · Playwright y Microsoft Edge | Abrió sesión, filtró el resumen, navegó desde móvil, registró un postulante, cargó y analizó un archivo, consultó D03, descargó un CSV, registró una revisión, cerró la recepción, registró resultado y abrió la nueva concesión. También completó el asistente de seis pasos, cargó bases y abrió un segundo proceso. |
| Escritorio, tablet y móvil | Resumen fotografiado a 1440 × 1000, 820 × 1080 y 390 × 844. Se comprobó que el documento no excediera el ancho de la ventana. |
| Paquetes de JavaScript | npm audit sobre el árbol resuelto informó 0 vulnerabilidades conocidas tras actualizar Vitest. |
| Instalación offline Windows x64, Python 3.14 | Se instalaron las dependencias en un entorno virtual nuevo con pip --no-index y las 35 ruedas incluidas. pip check terminó sin dependencias rotas. |
| Base inicial | integrity_check correcto y sin violaciones de claves foráneas. 600 expedientes, 168 proveedores registrados históricamente o en los módulos nuevos, 60 perfiles IFP, 100 alertas históricas pendientes, 3 postulaciones, 10 documentos incorporados y 3 concesiones de ejemplo. |

## Comprobaciones de negocio

- El panel deriva los importes de la API y permite contrastar la suma de los semestres con el total. La base inicial suma S/ 27 690 209,70 en contrataciones. El padrón histórico tiene 156 proveedores con contratos, mientras que el directorio de evaluación cubre 51 empresas y 9 personas naturales.
- El comparador detecta evidencia de garantía no localizada y diferencia de S/ 300 para Horizonte. Distingue esas señales del vínculo sintético de Nova. Una nota requiere criterio y referencia documental, y una calificación nueva obliga a renovar la revisión antes de registrar el resultado.
- Se probaron PDF, DOCX, XLSX, CSV y texto, referencias de página/párrafo/celda, rechazo de archivos inválidos, versión esperada y preservación de la lectura original al corregir un campo.
- Se comprobó cobertura incompleta del IFP, caducidad de fuentes, corte temporal, abstenciones, abonos parciales y escenarios sin modificación del original.
- La API rechaza sesiones ausentes y escrituras sin la cabecera esperada. Auditor recibe agregados y carece de acceso a originales, expedientes individuales y búsquedas. Un archivo SQLite ajeno se rechaza antes de modificar su contenido.
- El pronóstico experimental compara tres clasificadores sobre datos sintéticos. La prueba final comprende 576 observaciones futuras respecto del entrenamiento. Los resultados, falsos positivos y limitaciones están en [Validación de modelos](../VALIDACION_MODELOS.md).

## Repetición y límites

Los comandos de pruebas y el E2E opcional están en [Despliegue](../DESPLIEGUE.md). Las pruebas de Python y React se ejecutan sin acceso a internet una vez instaladas sus dependencias. El E2E usa un navegador Chromium local y crea su propia base temporal.

No se ejecutó Docker en esta máquina. La revisión visual cubrió los tres anchos del resumen y el recorrido funcional de la cafetería. Quedan pendientes pruebas de carga institucional, accesibilidad completa con lectores de pantalla y validación con funcionarios o proveedores reales. El inventario de funciones parciales está en [Alcance y evolución](../producto/ROADMAP.md).

## Verificación del incremento 3.1.0

Pasaron 42 pruebas Python y 12 de React. El frontend se compiló con Vite y el JS principal pesa 101,77 kB gzip. Microsoft Edge completó el arranque, la entrada pública, los controles de acceso y el recorrido de convocatoria hasta la concesión. Las capturas incluyen el portal en escritorio y 360 px, la bandeja y el menú móvil. La certificación WCAG AA sigue pendiente.
