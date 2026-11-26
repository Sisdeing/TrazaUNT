# Índice de fiabilidad del proveedor

La consulta del IFP toma las evidencias vigentes al corte de la demo. Para servicios se utilizan pesos de 15 para registro, 20 para sanciones, 15 para solvencia, 15 para obligaciones, 5 para litigios, 20 para historial y 10 para integridad. Los perfiles de servicios, bienes, obras y concesiones se validan al cargar `config/fiabilidad.yaml`.

IFP = 100 × suma(peso × subpuntaje) / suma(pesos evaluados). Cobertura = 100 × pesos evaluados / pesos aplicables. Con cobertura inferior a 50 % el resultado es «No evaluado». Para el histórico se usa la proporción de contratos cumplidos. Para solvencia se usa la menor de 1 y la razón capacidad disponible / importe propuesto. Sin importe comparable se omite ese factor.

La confianza es baja por debajo de 75 % de cobertura, media desde 75 % y alta desde 90 %. Para personas naturales se limita a media y se reduce el conjunto de dimensiones. La última evidencia de una dimensión reemplaza a la anterior aunque haya vencido. Un posible impedimento aparece junto con su referencia y vigencia. La presencia de un vínculo en revisión no reduce el índice por sí misma.

En Proveedores, abre un perfil, introduce un monto y pulsa evaluar para guardar una instantánea atribuida a tu cuenta. El directorio permite registro manual de evidencia sintética de sanciones u obligaciones. El padrón público nunca obtiene un IFP con factores simulados.

Consulta [Conflictos de interés](CONFLICTOS_INTERES.md) para interpretar relaciones y actuaciones.
