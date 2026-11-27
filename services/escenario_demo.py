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


# ---------------------------------------------------------------------------
# Convocatoria para la demo en vivo (v5.1): abierta y sin postulantes.
# La empresa postula y sube el kit de la carpeta «demo-en-vivo» durante la presentación.
# Una integrante del comité tiene el mismo nombre que la representante de Horizonte
# (coincidencia CI02, posible conflicto de intereses) y el kit trae diferencias que el
# análisis documental marca. Todo es ficticio.
# ---------------------------------------------------------------------------
CODIGO_VIVO = "FOT-DEMO-002"


def sembrar_convocatoria_vivo(motor):
    """Crea la convocatoria de la demo en vivo si aún no existe. Nunca toca una existente."""
    from pathlib import Path

    from db.convocatorias import Convocatoria
    from services.convocatorias import guardar_archivo, registrar, transaccion
    from services.trazadocs import extraer

    with transaccion(motor) as s:
        if s.scalar(select(Convocatoria.id).where(Convocatoria.codigo == CODIGO_VIVO)):
            return False
        c = Convocatoria(
            codigo=CODIGO_VIVO,
            nombre="Concesión del servicio de fotocopiado e impresiones",
            modalidad="Concesión de espacios",
            area="Biblioteca Central (demo)",
            objeto="Operación del módulo de fotocopiado e impresiones de la Biblioteca Central",
            descripcion="Recepción de propuestas para la demostración en vivo. Sin postulantes al inicio.",
            presupuesto=Decimal("1800.00"),
            duracion_meses=12,
            apertura=date(2026, 11, 26),
            cierre=date(2026, 12, 11),
            responsable="Coordinación de Bibliotecas (demo)",
            ubicacion="Biblioteca Central, primer piso (demo)",
            requisitos=["RUC", "Experiencia", "Plan operativo", "Garantía"],
            criterios=[
                dict(nombre="Propuesta operativa", peso=35.0),
                dict(nombre="Experiencia", peso=20.0),
                dict(nombre="Atención al estudiante", peso=15.0),
                dict(nombre="Contraprestación ofrecida", peso=30.0),
            ],
            intervinientes=[
                dict(nombre="Rosa Lumen Castillo (demo)", rol="Comité de selección", documento=None),
                dict(nombre="Jorge Paredes Núñez (demo)", rol="Comité de selección", documento=None),
                dict(nombre="Elena Varas Torres (demo)", rol="Supervisión", documento=None),
            ],
            estado="abierta",
        )
        s.add(c)
        s.flush()
        ruta = Path(__file__).resolve().parents[1] / "data/demo/vivo/bases-fotocopiado.pdf"
        if ruta.exists():
            raw = ruta.read_bytes()
            doc = guardar_archivo(s, c, None, "bases", ruta.name, None, raw, "Generador de demostración")
            for k, v in extraer(ruta.suffix, raw).items():
                setattr(doc, k, v)
        registrar(s, c, "Generador de demostración", "apertura_simulada",
                  "Inicio de la recepción de propuestas para la demostración en vivo.")
        return True
