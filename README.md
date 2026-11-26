# TrazaUNT 4.0 — trazabilidad e inteligencia histórica

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
