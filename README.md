# TrazaUNT 5.0 — trazabilidad, transparencia y control preventivo

TrazaUNT reconstruye quién intervino, con qué evidencia y por qué en cada contratación o concesión de la UNT, detecta coincidencias y señales de riesgo para revisión humana y publica la trazabilidad sin datos personales.

## Novedades 5.0

- **Tres perfiles.** *Universidad* crea convocatorias, revisa documentos, admite empresas y atiende alertas y coincidencias. *Empresa* consulta cómo va su convocatoria, su admisión y la revisión de sus documentos (y puede postular y presentar documentos). *Público* consulta, sin cuenta, contrataciones por año (registros sintéticos), convocatorias y la trazabilidad de expedientes.
- **Coincidencias automáticas persona–empresa** (CI01–CI06) al registrar una convocatoria, un interviniente o una empresa. Son alertas para revisión con nivel alto, medio o bajo, nunca conflictos confirmados. Ver [Coincidencias y perfiles](docs/PERFILES_Y_COINCIDENCIAS.md).
- **Datos CID integrados con procedencia**: 124 contratos de obra universitarios del Cuaderno de Obra Digital; los 130 asientos de la obra UNT se vinculan por código de contrato al expediente, con archivo, hoja y fila. Ver [Datos CID](docs/DATOS_CID.md).
- **Navegación simplificada**: Inicio, Alertas y coincidencias, Convocatorias, Expedientes y trazabilidad (integrado en la aplicación), Concesiones, Datos y fuentes, Bitácora. Se retiraron Conflictos de interés, Declaraciones, Proveedores, Reportes, Inteligencia económica, Gobierno del modelo y Pronóstico; **sus datos se conservan** y alimentan las coincidencias.
- **Controles de trazabilidad**: TZ06 (la misma cuenta formula el requerimiento, otorga la conformidad o registra el pago), TZ09 ampliada (pago mayor al monto del expediente), responsable registrado siempre como la cuenta autenticada y revisión de alertas con justificación mínima.

## Iniciar

En Windows x64 con Python 3.14 de 64 bits, ejecuta `iniciar.bat`. La raíz `http://127.0.0.1:8000/` muestra el portal público; **Acceso universidad** y **Acceso empresas** abren la pantalla de ingreso, que en modo demo ofrece accesos rápidos por perfil (solo desde el propio equipo).

Consulta [Despliegue](docs/DESPLIEGUE.md) y el [Guion de demostración](docs/GUION_DEMO.md). Para crear una cuenta de empresa: `python -m scripts.cuenta usuario empresa "Nombre" --ruc 00900000002`.

## Perfiles y seguridad

FastAPI sirve React compilado y consulta SQLite. Credenciales con scrypt, sesiones en cookies HttpOnly y cabecera anti-CSRF. El perfil empresa solo accede a `/api/empresa/*`; el público solo a `/api/publico/*`. Los nombres de personas naturales (RUC 10) y de miembros de comité se protegen en la vista; el registro original se conserva.

[Arquitectura](docs/ARQUITECTURA.md) · [Privacidad](docs/SEGURIDAD_PRIVACIDAD.md) · [Decisiones](docs/DECISIONES.md) · [Pendientes](docs/producto/ROADMAP.md) · [Cambios](CHANGELOG.md)

## Datos

530 expedientes públicos de la UNT (OCDS/SEACE), 11 604 procedimientos universitarios para análisis estadístico, contratos de obra CID y casos sintéticos identificados como (demo). Consulta [Datos históricos](docs/DATOS_HISTORICOS_4_0.md).

---

## Historial anterior (4.0)


TrazaUNT centraliza la revisión de contrataciones universitarias. El equipo consulta su bandeja, revisa evidencia y registra decisiones justificadas. El portal de transparencia publica exclusivamente agregados y permite descargar el historial anual en CSV.

## Iniciar

En Windows x64 con Python 3.14 de 64 bits, extrae la distribución y ejecuta `iniciar.bat`. La primera instalación puede usar las dependencias locales del ZIP. El lanzador abre el espacio de trabajo de la distribución de demostración. La raíz `http://127.0.0.1:8000/` muestra el portal público.

Consulta [Despliegue](docs/DESPLIEGUE.md) para instalación y cuentas, y el [Guion de demostración](docs/GUION_DEMO.md) para recorrer la cafetería.

## Perfiles y seguridad

Administración y análisis operan sobre los expedientes. Consulta dispone de accesos de lectura según sus permisos. Auditoría consulta agregados y Gobierno del modelo. Las decisiones requieren una cuenta y una justificación.

FastAPI sirve React compilado y consulta SQLite. La distribución incluye datos sintéticos identificados. Las credenciales se derivan con scrypt y las sesiones usan cookies HttpOnly. La evidencia y los datos de trabajo requieren autorización.

[Arquitectura](docs/ARQUITECTURA.md) · [Privacidad](docs/SEGURIDAD_PRIVACIDAD.md) · [Validación](docs/calidad/VALIDACION.md) · [Decisiones](docs/DECISIONES.md) · [Pendientes](docs/producto/ROADMAP.md) · [Cambios](CHANGELOG.md)

Las licencias de Inter, Lucide y React se incluyen con los recursos compilados. La licencia institucional del código queda por decidir.

## Nuevo módulo 3.2

[Guía de trazabilidad y alcance](docs/TRAZABILIDAD.md) · [Expedientes](docs/GESTION_EXPEDIENTES.md) · [Proceso](docs/PROCESS_MINING.md) · [Alertas](docs/MOTOR_ALERTAS_TRAZABILIDAD.md) · [Responsabilidades](docs/MATRIZ_RESPONSABILIDADES.md) · [Flujo](docs/FLUJO_PROCESOS.md).

## Actualización 4.0: información histórica real

La bandeja **Expedientes y trazabilidad** incluye 530 procedimientos públicos (529 integrados de los archivos entregados y una referencia adicional anterior), además de dos casos de demostración. Incluye información de 11 604 procesos OCDS de 51 entidades universitarias para análisis estadístico, fuentes por expediente, contratos, postores, comité cuando consta, padrón vinculado por RUC y puntuaciones experimentales de Isolation Forest. Consulta [Datos históricos](docs/DATOS_HISTORICOS_4_0.md). Los módulos heredados de demostración no han sido migrados y no representan estadísticas reales.

## Historial 3.3: procedencia pública

La bandeja de expedientes incluye tres procedimientos publicados de la UNT y dos expedientes sintéticos claramente identificados. Los registros públicos muestran enlaces, hitos documentados y controles locales pendientes de verificar; no suponen conformidades o pagos reales. Los demás módulos históricos conservan su dataset sintético y los modelos no se han reentrenado.

Descarga el JSONL anual en [Registro OCP / OECE](https://data.open-contracting.org/es/publication/135), y con el programa detenido ejecuta desde la carpeta TrazaUNT:

```powershell
.\.venv\Scripts\python.exe scripts/importar_ocds.py "C:\datos\2025.jsonl.gz"
```

El importador selecciona servicios de la UNT y evita duplicados por OCID. Consulta [procedencia pública y alcance](docs/DATOS_PUBLICOS_3_3.md).
