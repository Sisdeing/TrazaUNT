# Análisis de procesos

Se ordenan eventos persistidos por identificador de inserción y se construyen pares de actividades consecutivas. `Counter` calcula las frecuencias de cada par. La interfaz muestra una tabla de sucesión directa del expediente (no descubrimiento avanzado ni PM4Py). Las reglas comparan controles puntuales y fases anteriores; no se calculan métricas globales de conformidad ni alineamientos. La hora de registro y la efectiva se almacenan separadamente, aunque la API aún no expone la edición de fecha efectiva.
