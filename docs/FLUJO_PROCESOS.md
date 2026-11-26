# Flujo de procesos

```mermaid
stateDiagram-v2
 [*] --> pendiente
 pendiente --> en_ejecucion: iniciar
 en_ejecucion --> en_revision: verificar
 en_revision --> observada: observar
 observada --> en_subsanacion: responder
 en_subsanacion --> en_revision: cerrar observación
 en_revision --> validada: visto bueno
 validada --> cerrada: cierre
 cerrada --> reabierta: justificar reapertura
 reabierta --> en_ejecucion: iniciar
```

El servicio valida estados, revisión optimista y requisitos. Las transacciones `BEGIN IMMEDIATE` serializan modificaciones SQLite. La fase 7 requiere conformidad cerrada y libre de observaciones y el pago se registra como evidencia, no como transacción bancaria. Se usa secuencia lineal para las dos plantillas iniciales; excepciones autorizadas y caminos paralelos no implementados.
