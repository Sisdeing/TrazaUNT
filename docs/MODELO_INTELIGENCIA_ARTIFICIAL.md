# Algoritmos y explicabilidad

R01–R06 conservan la semántica de la versión 2. R01 usa normalización del objeto y ventana temporal. R02 detecta concentración de adjudicaciones por cantidad en una entidad y año. R03 examina soporte de pagos. R04 compara monto con una banda didáctica. R05 detecta incoherencias de fechas. R06 relaciona antigüedad del proveedor e importe elevado.

Isolation Forest observa monto, frecuencia anual, concentración por entidad, ratio frente al promedio del objeto, días desde constitución y número de postores. La semilla, número de árboles, muestras y mínimo de registros están en `config/reglas.yaml`. La rareza se calcula limitando 2 × (−score_samples − 0,5) al intervalo [0,1]. La ponderación por defecto combina 70 % de reglas y 30 % de rareza. El expediente conserva los aportes de ambos.

Esta evaluación histórica observa el universo completo. No debe usarse como una predicción en la fecha original del contrato. Las etiquetas inyectadas se reservan a la matriz de confusión de las reglas. Las decisiones humanas no se convierten en etiquetas.

La predicción temporal de cuotas tiene un conjunto de entrenamiento independiente y controles de madurez. Las explicaciones documentales utilizan reglas locales con ubicación de evidencia. TrazaAssistant consulta plantillas y registros autorizados. El funcionamiento de la demostración no requiere un LLM externo.
