"""Historial de demostración para dos empresas de la convocatoria de la cafetería (v5.1).

* Operaciones Horizonte (demo): contratos 2025 con antecedentes que las reglas detectan
  por sí solas: tres órdenes de proyectores de S/ 14 900 en 10 días (suman más de 8 UIT,
  posible fraccionamiento) y un pago sin conformidad.
* Servicios Campus Aurora (demo): historial limpio, para contrastar.

Son registros sintéticos de demostración (código «DEMO-…», entidades «SIMULADA») y solo
se cargan en el entorno demo. La carga es idempotente: si ya existen, no se repite.
"""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from db.database import obtener_sesion
from db.models import Contratacion, Pago, Proveedor

# (código, ruc, entidad, fecha, objeto, monto, tipo de proceso, postores, pago con conformidad)
CONTRATOS = [
    ("DEMO-HZN-001", "00900000002", 3, "2025-02-12", "Servicio de limpieza de ambientes", "28600.00", "Proceso simulado A", 4, True),
    ("DEMO-HZN-002", "00900000002", 5, "2025-04-03", "Mantenimiento de equipos de cómputo", "19800.00", "Proceso simulado B", 3, True),
    ("DEMO-HZN-003", "00900000002", 3, "2025-06-09", "Adquisición de proyectores multimedia", "14900.00", "Proceso simulado B", 2, True),
    ("DEMO-HZN-004", "00900000002", 3, "2025-06-12", "Adquisición de proyectores multimedia", "14900.00", "Proceso simulado B", 2, True),
    ("DEMO-HZN-005", "00900000002", 3, "2025-06-18", "Adquisición de proyectores multimedia", "14900.00", "Proceso simulado B", 2, True),
    ("DEMO-HZN-006", "00900000002", 3, "2025-08-21", "Servicio de cafetería para eventos", "9800.00", "Proceso simulado A", 3, False),
    ("DEMO-HZN-007", "00900000002", 5, "2025-10-02", "Mantenimiento de equipos de cómputo", "22400.00", "Proceso simulado B", 4, True),
    ("DEMO-AUR-001", "00900000001", 2, "2025-03-05", "Servicio de cafetería institucional", "31200.00", "Proceso simulado A", 5, True),
    ("DEMO-AUR-002", "00900000001", 4, "2025-05-20", "Refrigerios para eventos académicos", "12600.00", "Proceso simulado B", 4, True),
    ("DEMO-AUR-003", "00900000001", 6, "2025-07-14", "Catering para seminario internacional", "8400.00", "Proceso simulado B", 3, True),
    ("DEMO-AUR-004", "00900000001", 2, "2025-09-08", "Servicio de cafetería institucional", "33000.00", "Proceso simulado A", 5, True),
]


def sembrar_historial_demo(motor):
    """Agrega el historial de demostración si las empresas existen y aún no lo tienen."""
    with obtener_sesion(motor) as s:
        existentes = set(s.scalars(select(Contratacion.codigo).where(Contratacion.codigo.like("DEMO-%"))))
        proveedores = {p.ruc: p for p in s.scalars(select(Proveedor).where(Proveedor.ruc.in_({c[1] for c in CONTRATOS})))}
        nuevos = 0
        for codigo, ruc, entidad, fecha, objeto, monto, tipo, postores, conforme in CONTRATOS:
            if codigo in existentes or ruc not in proveedores:
                continue
            f = date.fromisoformat(fecha)
            c = Contratacion(codigo=codigo, entidad_id=entidad, proveedor_id=proveedores[ruc].id, objeto=objeto,
                             monto=Decimal(monto), fecha=f, tipo_proceso=tipo, n_postores=postores,
                             es_anomalia_real=False, tipos_anomalia_real=[])
            s.add(c)
            s.flush()
            s.add(Pago(contratacion_id=c.id, monto=Decimal(monto), fecha_pago=f + timedelta(days=25),
                       tiene_conformidad=conforme, tiene_comprobante=True))
            nuevos += 1
        return nuevos
