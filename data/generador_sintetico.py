"""Datos sintéticos reproducibles; este módulo no consulta ni modifica la BD.

Los importes de los escenarios son ejemplos didácticos. El valor de S/ 50 000
NO representa un umbral legal ni una cantidad de UIT. Los parámetros del
detector se definen por separado en config/reglas.yaml.

``es_anomalia_real`` y ``tipos_anomalia_real`` son etiquetas de evaluación:
no deben llegar al motor de reglas, al modelo de IA ni a la vista del analista.
"""

from datetime import date, timedelta
from decimal import Decimal
import random
from typing import Any

from faker import Faker


def generar_datos(semilla: int = 42, n_normales: int = 500) -> dict[str, list[dict[str, Any]]]:
    """Genera ``n_normales`` contrataciones normales y 100 casos inyectados.

    Con la misma semilla, cantidad y versión de Faker devuelve los mismos
    valores. No utiliza la fecha del sistema ni el generador aleatorio global.
    Los identificadores explícitos permiten insertar las tablas en orden.
    """
    if not isinstance(semilla, int) or isinstance(semilla, bool):
        raise ValueError("La semilla debe ser un número entero.")
    if not isinstance(n_normales, int) or isinstance(n_normales, bool) or n_normales < 100:
        raise ValueError("n_normales debe ser un entero mayor o igual a 100.")

    azar = random.Random(semilla)
    falso = Faker("es_ES")
    falso.seed_instance(semilla)

    datos: dict[str, list[dict[str, Any]]] = {
        "entidades": [], "proveedores": [], "contrataciones": [], "pagos": []
    }
    for numero in range(1, 12):
        datos["entidades"].append({
            "id": numero,
            "codigo": f"ENT-SIM-{numero:03d}",
            "nombre": f"Entidad pública SIMULADA {numero:02d}",
        })

    def agregar_proveedor(constitucion: date | None = None) -> int:
        """Los RUC con prefijo 00 son identificadores ficticios, no validables."""
        numero = len(datos["proveedores"]) + 1
        if constitucion is None:
            constitucion = date(2010, 1, 1) + timedelta(days=azar.randint(0, 8 * 365))
        datos["proveedores"].append({
            "id": numero,
            "ruc": f"00{numero:09d}",
            "razon_social": f"SIMULADO {numero:03d} · {falso.company()} (demo)",
            "fecha_constitucion": constitucion,
            "domicilio": f"SIMULADO · {falso.street_address()} · Ciudad ficticia, Perú",
            "representante": f"SIMULADO · {falso.name()} (demo)",
        })
        return numero

    def agregar_contratacion(
        entidad: int,
        proveedor: int,
        objeto: str,
        monto: Decimal,
        fecha: date,
        anomalia: str | None = None,
        fecha_pago: date | None = None,
        conformidad: bool = True,
        comprobante: bool = True,
    ) -> None:
        """Añade una contratación y un pago; la etiqueta no altera sus campos."""
        numero = len(datos["contrataciones"]) + 1
        datos["contrataciones"].append({
            "id": numero,
            "codigo": f"EXP-{fecha.year}-{numero:05d}",
            "entidad_id": entidad,
            "proveedor_id": proveedor,
            "objeto": objeto,
            "monto": monto,
            "fecha": fecha,
            # Son categorías ficticias: no califican legalmente un procedimiento.
            "tipo_proceso": azar.choice(["Proceso simulado A", "Proceso simulado B"]),
            "n_postores": azar.randint(3, 10),
            "es_anomalia_real": anomalia is not None,
            "tipos_anomalia_real": [anomalia] if anomalia else [],
        })
        datos["pagos"].append({
            "id": len(datos["pagos"]) + 1,
            "contratacion_id": numero,
            "monto": monto,
            "fecha_pago": fecha_pago if fecha_pago is not None else fecha + timedelta(days=30),
            "tiene_conformidad": conformidad,
            "tiene_comprobante": comprobante,
        })

    # 1. Población de referencia: proveedores antiguos, pagos sustentados y
    # distribución equilibrada. El dinero se genera en céntimos, sin usar float.
    for _ in range(100):
        agregar_proveedor()
    objetos = [
        "Equipamiento de laboratorio", "Mantenimiento de biblioteca",
        "Licencias de software académico", "Mobiliario para aulas",
        "Servicio de conectividad", "Material bibliográfico",
        "Material de oficina", "Servicio de limpieza",
    ]
    for i in range(n_normales):
        centimos = azar.randint(500_000, 8_000_000)
        # Evitar la banda que se utilizará en el escenario de cercanía al umbral.
        if 4_750_000 <= centimos < 5_000_000:
            centimos += 500_000
        fecha = date(2025, 1, 1) + timedelta(days=azar.randint(0, 300))
        agregar_contratacion(
            entidad=i % 10 + 1,
            proveedor=((i // 10) * 7 + i % 10) % 100 + 1,
            objeto=azar.choice(objetos),
            monto=Decimal(centimos) / Decimal("100"),
            fecha=fecha,
            fecha_pago=fecha + timedelta(days=azar.randint(7, 45)),
        )

    # 2. Fraccionamiento: cinco grupos de cuatro contratos de S/ 15 000.
    # En cada grupo coinciden entidad, proveedor y objeto dentro de nueve días.
    for grupo in range(5):
        proveedor = agregar_proveedor()
        for parte in range(4):
            agregar_contratacion(
                grupo + 1, proveedor, f"Equipos de laboratorio, lote {grupo + 1}",
                Decimal("15000.00"), date(2025, 3, 1) + timedelta(days=parte * 3),
                "fraccionamiento",
            )

    # 3. Dominio: una entidad separada adjudica sus 30 contratos al mismo proveedor.
    proveedor_dominante = agregar_proveedor()
    for i in range(30):
        agregar_contratacion(
            11, proveedor_dominante, azar.choice(objetos), Decimal("60000.00"),
            date(2025, 2, 1) + timedelta(days=i * 5), "proveedor_dominante",
        )

    # 4. Pagos sin sustento: cinco sin conformidad, cinco sin comprobante y
    # cinco sin ambos documentos. No se crean archivos documentales ficticios.
    for i in range(15):
        agregar_contratacion(
            i % 10 + 1, agregar_proveedor(), "Mantenimiento de ambientes",
            Decimal("25000.00"), date(2025, 6, 1) + timedelta(days=i * 3),
            "pagos_sin_sustento", conformidad=i % 3 == 1, comprobante=i % 3 == 0,
        )

    # 5. Montos entre el 95 % y el 100 % de un umbral exclusivamente didáctico.
    for i in range(15):
        agregar_contratacion(
            i % 10 + 1, agregar_proveedor(), "Equipamiento de aulas",
            Decimal(azar.randint(4_750_000, 4_999_999)) / Decimal("100"),
            date(2025, 7, 1) + timedelta(days=i), "monto_cercano_umbral",
        )

    # 6. Fechas incoherentes: cinco pagos anteriores al contrato y cinco
    # contratos anteriores a la constitución del proveedor.
    for i in range(10):
        fecha = date(2025, 8, 1) + timedelta(days=i * 2)
        proveedor = agregar_proveedor(fecha + timedelta(days=20) if i >= 5 else None)
        agregar_contratacion(
            i % 10 + 1, proveedor, "Adquisición de material bibliográfico",
            Decimal("30000.00"), fecha, "fechas_incoherentes",
            fecha_pago=fecha - timedelta(days=10) if i < 5 else fecha + timedelta(days=30),
        )

    # 7. Proveedor reciente: contrato de S/ 250 000 a los 14 días de constituirse.
    for i in range(10):
        fecha = date(2025, 9, 1) + timedelta(days=i * 2)
        agregar_contratacion(
            i % 10 + 1, agregar_proveedor(fecha - timedelta(days=14)),
            "Equipamiento especializado de investigación", Decimal("250000.00"),
            fecha, "proveedor_reciente_contrato_grande",
        )

    return datos
