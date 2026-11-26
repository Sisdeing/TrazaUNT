# Diccionario de datos

| Campo | Unidad o dominio | Interpretación |
|---|---|---|
| ruc | Texto de 11 dígitos | El prefijo 00 identifica la simulación. La consulta pública acepta sólo personas jurídicas y comprueba el dígito verificador. |
| contrataciones.monto | PEN, dos decimales | Importe del expediente histórico. |
| postulaciones.oferta | PEN | En el escenario de cafetería es contraprestación mensual a favor de la universidad. |
| documentos.sha256 | Hexadecimal | Identidad de los bytes recibidos. El mismo nombre admite versiones distintas. |
| documentos.campos | Lista JSON | Campo, valor original, fragmento, ubicación, confianza y revisión. Un valor efectivo puede incorporar una corrección. |
| version_bases | Entero | Edición del instrumento aplicada a una propuesta o evaluación. |
| score | 0–100 | Índice retrospectivo del proceso. IFP y el pronóstico tienen modelos independientes. |
| evidencias_ifp | Referencia, corte, fin de vigencia y origen | Sustento de cada dimensión habilitada. |
| cuota / abono | PEN por vencimiento / PEN por pago | El abono se imputa a una cuota identificada. |
| pronostico | Corte, versión y horizonte | Categoría experimental derivada de pagos observables. |
| fecha de auditoría | UTC en almacenamiento | La interfaz presenta la hora de Lima. |

Los nombres de las columnas y las restricciones de integridad están en los modelos declarativos de `db/`. Una evidencia ausente o vencida deja el factor pendiente. Las etiquetas sintéticas de evaluación se consultan sólo para métricas agregadas.
