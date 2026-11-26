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
