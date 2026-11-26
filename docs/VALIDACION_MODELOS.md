# Validación de modelos

La evaluación histórica de reglas opera sobre 600 expedientes con etiquetas inyectadas. El endpoint /api/metricas informa la matriz agregada. El componente de Isolation Forest se ajusta al mismo universo retrospectivo y carece de una evaluación prospectiva independiente en esta entrega.

Para mora, el generador crea observaciones mensuales independientes de las etiquetas del expediente histórico. Se usaron 2 112 observaciones de entrenamiento, 528 de validación y 576 de prueba. Los cortes de prueba van de enero a diciembre de 2025 y dejan madurar la etiqueta tras cada vencimiento. La selección por precisión promedio en validación favoreció la regresión logística.

| Modelo | Precisión promedio en prueba | ROC-AUC | F1 | Brier |
|---|---:|---:|---:|---:|
| Frecuencia de referencia | 0,4253 | 0,5000 | 0,5968 | 0,2568 |
| Regresión logística | 0,6438 | 0,7723 | 0,7250 | 0,1984 |
| Random Forest | 0,6328 | 0,7698 | 0,7297 | 0,1867 |

Con el umbral de revisión seleccionado en validación, la regresión logística tuvo 175 verdaderos negativos, 156 falsos positivos, 17 falsos negativos y 228 verdaderos positivos. La carga de revisión derivada de los falsos positivos es material. La pantalla presenta categorías experimentales y variables observadas. El Brier por sí solo no demuestra calibración adecuada para exponer probabilidades personales o institucionales.

Se pueden reproducir los cálculos con `python -c "from services.predicciones import entrenar; print(entrenar()[1])"` dentro del entorno instalado. El generador supone persistencia temporal de tensiones financieras y no representa un estudio de proveedores reales.
