# 5.1.0 — interfaz más simple

- Trazabilidad reescrita dentro de la aplicación React (ya no se usa la página aparte en un marco): barra de 8 pasos con colores por estado, requisitos con «Subir» y «Verificar» en cada fila, un solo botón de «siguiente paso» según el estado de la fase y el resto en «Más acciones», 4 pestañas (Fases, Alertas, Documentos, Historial; «Fuente pública» solo en registros públicos). La lista muestra primero los expedientes en trámite.
- Convocatorias: cada empresa postulante abre su ficha con datos, decisión de admisión (Admitir / Observar / No admitir), sus documentos con la evidencia extraída y sus coincidencias. Se quitó la pestaña «Documentos»; las bases tienen sus documentos en la pestaña Bases; Comparación y Revisiones se agrupan en «Evaluación».
- Menú: sale el grupo «Información». «¿De dónde salen los datos?» queda al pie de la barra lateral y la Bitácora de auditoría solo la ve Administración.
- **Centro de alertas**: reúne reglas R01–R06, coincidencias CI01–CI06 y alertas TZ en cinco categorías (posible fraccionamiento, posible colusión, posible conflicto de intereses, concentración de contrataciones, otras señales de control). Cada alerta muestra prioridad, estado (pendiente, en revisión, revisada, descartada), empresas, proceso, indicadores, evidencias, explicación y qué revisar. Los patrones repetidos (R01, R02) se agrupan en un solo caso. Filtros por categoría, prioridad, estado, fechas y texto, con filtros activos visibles. Nueva tabla aditiva `seguimiento_alertas` para «en revisión». Rutas `/api/centro-alertas`.
- **Empresas**: historial individual por empresa (`/api/fichas-empresa`) con participaciones, contratos, entidades, montos, postulaciones, alertas por tipo y en el tiempo, línea de tiempo, gráficos e índice de fiabilidad (IFP) con «Evaluar de nuevo». Solo datos existentes; lo que falta se muestra como «no disponible».
- **Paleta UNT** aplicada a toda la interfaz (`frontend/src/unt.css`, `frontend/src/ui/`): navegación #000C4B, botones #12377B, acentos #0A2FFF, énfasis #FDF107, texto #1B1811, prioridad alta #D8261A, favorable #0C8F3D, advertencia #E6AD09.
- **Usabilidad (Nielsen)**: estados de carga y avisos de confirmación, confirmación antes de decisiones irreversibles, filtros activos con «×» y «Limpiar todo», mensajes de error comprensibles, ayudas sobre tipos de alertas y criterios, estados vacíos explicados, tablas ordenables, términos sin jerga.
- Se quitaron los desplegables que mostraban código (JSON de evidencias, variables de IA, huellas en hexadecimal); la página antigua `/trazabilidad` redirige a la nueva.
- Corrección: las operaciones de escritura de la API de proveedores e integridad (p. ej. «Evaluar de nuevo» del IFP) fallaban con «database is locked» porque la transacción se cerraba después de responder.
- R01 y R04 usan 8 UIT (UIT 2026 = S/ 5,500 según DS 301-2025-EF): umbral de referencia de S/ 44,000.
- Historial de demostración: Operaciones Horizonte (demo) tiene contratos 2025 con antecedentes (posible fraccionamiento y pago sin conformidad) y Servicios Campus Aurora (demo) un historial limpio. En cada convocatoria, la ficha del postulante muestra sus antecedentes en otros procesos.
- **Demo en vivo**: convocatoria FOT-DEMO-002 abierta y sin postulantes, carpeta `demo-en-vivo/` con el kit que sube la empresa y `iniciar-demo-limpia.bat` para empezar con una base nueva.
- 68 pruebas Python y 22 de React.

# 5.0.0 — perfiles, coincidencias y CID

- Perfiles Universidad, Empresa y Público; acceso de demostración por perfil (solo local y en modo demo); cuentas de empresa vinculadas a un RUC.
- Detección automática de coincidencias persona–empresa (CI01 DNI, CI02 nombre completo, CI03 apellidos, CI04 domicilio, CI05 representante, CI06 vínculo documentado) con revisión humana justificada e historial.
- Admisión de postulantes (admitida, observada, no admitida) con motivo visible para la empresa; un postulante no admitido no puede ser seleccionado.
- Integración CID: `scripts/cid_extraer.py`, `scripts/cid_compactar.py`, `data/publicos/cid_universidades.json.gz`; asientos vinculados por código de contrato con archivo, hoja y fila.
- Portal público con contrataciones por año, convocatorias y trazabilidad de expedientes sin datos personales.
- Navegación simplificada; trazabilidad integrada en la aplicación; secciones retiradas sin borrar datos.
- TZ06 (funciones que deberían estar separadas), TZ09 frente al monto del expediente, responsable = cuenta autenticada, justificación mínima en revisiones; protección de personas naturales en la vista interna.
- 60 pruebas Python y 15 de React.

# 3.3.0 — expedientes y fuentes públicas

- Tres procedimientos históricos con referencias públicas; importador offline OCDS JSONL/Gzip.
- Procedencia y fechas efectivas diferenciadas; ausencia de evidencia no se interpreta como incumplimiento.
- Nombres ficticios naturales, interfaz renovada, búsqueda y filtro de procedencia.
- Conservación de módulos previos, sin reentrenamiento de modelos.

# 3.2.0 — prototipo

- Nuevo flujo de expedientes y fases, documentos versionados, observaciones, actuaciones, alertas TZ e informe.
- Ver `docs/TRAZABILIDAD.md` para límites y pendientes.

# Registro de cambios

## 3.1.0

- Inicio en Mi bandeja para los perfiles operativos y navegación técnica por rol.
- Portal público con agregados, estados, alertas atendidas y descarga CSV.
- Centro de confianza, tokens de marca y aviso de entorno.
- Configuración del acceso automático y visibilidad del pronóstico.

## 4.0 — datos históricos aportados
- 530 expedientes de procedencia pública y dos de demostración; integración de 529 procedimientos desde archivos recibidos, más una referencia anterior.
- 11 604 procedimientos universitarios OCDS deduplicados, evidencia Excel, padrón vinculado y modelo experimental de atipicidad.
- Paginación, filtro anual, ficha de evidencia pública, resumen de cobertura y evaluación temporal.
- Conserva módulos heredados sintéticos y sus límites; no acredita actuaciones internas por datos faltantes.
