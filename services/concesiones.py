"""Contraprestaciones mensuales, abonos imputados y escenarios del concesionario."""

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from db.integridad import Abono, Concesion, Cuota, Obligacion
from db.models import Proveedor

CENTIMO = Decimal("0.01")


def dinero(valor):
    return Decimal(str(valor)).quantize(CENTIMO, rounding=ROUND_HALF_UP)


def programar_cuotas(s, concesion):
    """La primera mensualidad vence al fin del mes, o al término si es anterior."""
    mes = concesion.inicio.replace(day=1)
    while mes <= concesion.fin:
        cierre = mes.replace(day=monthrange(mes.year, mes.month)[1])
        s.add(
            Cuota(
                concesion_id=concesion.id,
                fecha=min(cierre, concesion.fin),
                exigible=concesion.contraprestacion,
            )
        )
        mes = cierre + timedelta(days=1)


def abrir_concesion(
    sesion,
    convocatoria_id,
    codigo_convocatoria,
    espacio,
    area,
    ruc,
    importe,
    inicio,
    fin,
):
    proveedor = sesion.scalar(select(Proveedor).where(Proveedor.ruc == ruc))
    if (
        proveedor is None
        or fin < inicio
        or dinero(importe) <= 0
        or (fin - inicio).days > 36525
    ):
        raise ValueError(
            "Verifique las fechas, el proveedor y la contraprestación mensual."
        )
    c = Concesion(
        convocatoria_id=convocatoria_id,
        codigo="CON-" + codigo_convocatoria,
        espacio=espacio,
        area=area,
        proveedor_id=proveedor.id,
        inicio=inicio,
        fin=fin,
        contraprestacion=dinero(importe),
    )
    sesion.add(c)
    sesion.flush()
    programar_cuotas(sesion, c)
    sesion.add(
        Obligacion(
            concesion_id=c.id, nombre="Revisión de inicio de operación", vence=inicio
        )
    )
    return c.id


def sembrar_concesiones(s, proveedores):
    for i, p in enumerate(proveedores):
        codigo = f"HIST-DEMO-{i + 1:02d}"
        if s.scalar(select(Concesion.id).where(Concesion.codigo == codigo)):
            continue
        c = Concesion(
            convocatoria_id=None,
            codigo=codigo,
            espacio=["Quiosco Norte", "Sala de copiado", "Punto editorial"][i],
            area="Gestión patrimonial",
            proveedor_id=p.id,
            inicio=date(2026, 8, 1),
            fin=date(2026 if i == 2 else 2027, 10, 31),
            contraprestacion=dinero([1600, 1200, 850][i]),
            garantia_hasta=date(2026 if i == 1 else 2027, 9, 30),
            ingresos=dinero([12150, 8140, 5090][i]),
            costos=dinero([8100, 6800, 3500][i]),
        )
        s.add(c)
        s.flush()
        programar_cuotas(s, c)
        s.flush()
        for j, cuota in enumerate(
            s.scalars(
                select(Cuota).where(Cuota.concesion_id == c.id).order_by(Cuota.fecha)
            )
        ):
            if cuota.fecha > date(2026, 11, 23) or (i == 1 and j > 0):
                continue
            s.add(
                Abono(
                    cuota_id=cuota.id,
                    fecha=cuota.fecha,
                    monto=cuota.exigible,
                    referencia=f"REC-{codigo}-{j + 1:02d}",
                    responsable="Tesorería (demo)",
                )
            )
        s.add(
            Obligacion(
                concesion_id=c.id,
                nombre="Inspección de operación",
                vence=date(2026, 10, 15),
                cumplida=None if i == 1 else date(2026, 10, 14),
            )
        )
        if i != 2:
            s.add(
                Obligacion(
                    concesion_id=c.id,
                    nombre="Presentación del reporte mensual",
                    vence=date(2026, 11, 30),
                )
            )


def ficha_concesion(s, c, corte, detalle=True):
    p = s.get(Proveedor, c.proveedor_id)
    estado = (
        "Programada" if corte < c.inicio else "Vencida" if corte > c.fin else "Activa"
    )
    base = dict(
        id=c.id,
        codigo=c.codigo,
        espacio=c.espacio,
        proveedor=p.razon_social,
        ruc=p.ruc,
        proveedor_id=p.id,
        area=c.area,
        inicio=c.inicio,
        fin=c.fin,
        contraprestacion=c.contraprestacion,
        estado=estado,
        convocatoria_id=c.convocatoria_id,
        corte=corte,
        origen="simulado",
    )
    if not detalle:
        return base
    pagos = []
    esperado = registrado = saldo = Decimal(0)
    dias_mora = 0
    abonos = {}
    for a in s.scalars(
        select(Abono)
        .join(Cuota)
        .where(Cuota.concesion_id == c.id, Abono.fecha <= corte)
    ):
        abonos[a.cuota_id] = abonos.get(a.cuota_id, Decimal(0)) + a.monto
    for cuota in s.scalars(
        select(Cuota).where(Cuota.concesion_id == c.id).order_by(Cuota.fecha)
    ):
        abonado = abonos.get(cuota.id, Decimal(0))
        exigible = cuota.fecha <= corte
        pendiente = max(Decimal(0), cuota.exigible - abonado)
        if exigible:
            esperado += cuota.exigible
            registrado += min(cuota.exigible, abonado)
            if cuota.fecha < corte:
                saldo += pendiente
                if pendiente:
                    dias_mora = max(dias_mora, (corte - cuota.fecha).days)
        estado_cuota = (
            "Pagada"
            if not pendiente
            else "Vencida"
            if cuota.fecha < corte
            else "Por vencer"
        )
        pagos.append(
            dict(
                id=cuota.id,
                fecha=cuota.fecha,
                exigible=cuota.exigible,
                pagado=abonado,
                estado=estado_cuota,
            )
        )
    obligaciones = []
    for o in s.scalars(
        select(Obligacion)
        .where(Obligacion.concesion_id == c.id)
        .order_by(Obligacion.vence)
    ):
        estado_o = (
            "Cumplida"
            if o.cumplida and o.cumplida <= corte
            else "Vencida"
            if o.vence < corte
            else "Programada"
        )
        obligaciones.append(
            dict(id=o.id, nombre=o.nombre, vence=o.vence, estado=estado_o)
        )
    alertas = []
    if corte > c.fin:
        alertas.append(
            dict(codigo="C01", motivo="La fecha de término registrada ya pasó.")
        )
    if saldo:
        alertas.append(
            dict(
                codigo="C02",
                motivo=f"S/ {saldo:,.2f} en cuotas vencidas pendientes de cobro.",
            )
        )
    if c.garantia_hasta and c.garantia_hasta < corte <= c.fin:
        alertas.append(
            dict(
                codigo="C03",
                motivo="La garantía registrada venció durante la concesión.",
            )
        )
    if any(o["estado"] == "Vencida" for o in obligaciones):
        alertas.append(
            dict(
                codigo="C11",
                motivo="Hay obligaciones de supervisión vencidas sin conformidad registrada.",
            )
        )
    cumplimiento = round(100 * registrado / esperado, 2) if esperado else None
    return dict(
        **base,
        esperado=esperado,
        registrado=registrado,
        saldo_vencido=saldo,
        cumplimiento=cumplimiento,
        dias_mora=dias_mora,
        garantia_hasta=c.garantia_hasta,
        pagos=pagos,
        obligaciones=obligaciones,
        alertas=alertas,
        ingresos=c.ingresos,
        costos=c.costos,
    )


def simular(ingresos, costos, contraprestacion):
    escenarios = []
    for nombre, variacion_ingresos, variacion_costos in [
        ("Pesimista", "0.85", "1.10"),
        ("Base", "1", "1"),
        ("Optimista", "1.15", "0.95"),
    ]:
        i = dinero(ingresos * Decimal(variacion_ingresos))
        c = dinero(costos * Decimal(variacion_costos))
        flujo = i - c - contraprestacion
        escenarios.append(
            dict(
                nombre=nombre,
                ingresos=i,
                costos=c,
                contraprestacion=contraprestacion,
                flujo=flujo,
                revision=flujo < 0,
            )
        )
    return dict(
        escenarios=escenarios,
        perspectiva="Flujo mensual del concesionario",
        moneda="PEN",
    )
