# Perfiles y coincidencias persona–empresa (5.0)

## Perfiles

| Perfil | Quién | Qué ve y hace | Qué no ve |
|---|---|---|---|
| Universidad (analista, administración) | Personal de la UNT | Crea convocatorias, registra intervinientes, revisa documentos, decide la admisión de empresas, revisa alertas y coincidencias, gestiona expedientes y concesiones, consulta fuentes y bitácora | — |
| Universidad (auditor) | Control interno | Indicadores agregados del Inicio y Centro de confianza | Expedientes individuales |
| Empresa | Representante de un postulante | Convocatorias abiertas, sus postulaciones, etapa del proceso, su admisión con el motivo, el estado de revisión de sus documentos, su historial; puede postular y presentar documentos mientras la recepción está abierta | Otros postulantes, análisis interno de documentos, coincidencias, nombres de intervinientes |
| Público | Cualquier persona, sin cuenta | Contrataciones por año (registros sintéticos), convocatorias con estado y resultado, trazabilidad de expedientes: fases, fechas, documentos con huella SHA-256, fuentes y resumen del cuaderno de obra | Nombres de personas, responsables, observaciones en texto libre, alertas individuales, coincidencias |

El acceso rápido por perfil (`/api/sesion/demo`) solo funciona con `TRAZA_ENTORNO=demo` y desde el propio equipo.

## Coincidencias

Se calculan automáticamente al crear o editar una convocatoria, al registrar un postulante (por la universidad o por la propia empresa) y al iniciar la aplicación. Cada resultado conserva fuente, evidencia y criterio, y se marca *no vigente* si deja de cumplirse (nunca se borra).

| Código | Nivel | Señal | Criterio |
|---|---|---|---|
| CI01 | Alta | Documento de identidad coincidente | DNI del interviniente igual al DNI contenido en el RUC 10 de una persona natural postulante |
| CI02 | Media | Nombre completo coincidente | Nombre normalizado igual (sin tildes, mayúsculas ni anotaciones) entre interviniente y representante o titular |
| CI03 | Baja | Coincidencia parcial de apellidos | Al menos un término distintivo en común; coincidencia débil |
| CI04 | Media | Postulantes con el mismo domicilio fiscal | Domicilio normalizado igual; se excluyen domicilios genéricos repetidos por más de tres empresas |
| CI05 | Media | Postulantes con el mismo representante | Nombre normalizado igual |
| CI06 | Alta | Vínculo documentado | Parentesco o participación societaria verificada en el registro de integridad |

**Revisión humana.** Cada coincidencia se cierra como *Aclarada sin incidencia* o *Derivada a revisión de integridad*, con una justificación de al menos 15 caracteres. Todas las decisiones quedan en el historial de la coincidencia y en el de la convocatoria. Ninguna coincidencia constituye un conflicto de intereses confirmado.

## Escenario de demostración

En la convocatoria CAF-DEMO-001 se detectan cuatro coincidencias: CI02 (miembro del comité con el mismo nombre que el representante de Aurora), CI03 (apellido Lumen compartido), CI04 (Horizonte y Nova comparten domicilio) y CI06 (vínculo documentado Lumen–Nova). Todos los nombres son ficticios.

## Controles de trazabilidad relacionados

- **TZ06**: la misma cuenta formula el requerimiento y otorga la conformidad, otorga la conformidad y registra el pago, o formula el requerimiento y registra el pago.
- **TZ09**: el pago supera el monto registrado del expediente (además de la diferencia entre lo pagado y lo autorizado).
- El responsable de cada actuación es la cuenta autenticada; el texto libre solo se usa para *asignar* responsables.
