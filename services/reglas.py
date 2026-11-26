"""Seis reglas transparentes. Producen hallazgos para revisión, no acusaciones.

Las funciones trabajan con diccionarios de datos operativos y no consultan
etiquetas de evaluación. Este módulo no calcula scores ni guarda alertas.
Ejemplo de ejecución: python -m services.reglas
"""

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import json
import re
import unicodedata
from pathlib import Path

from services.configuracion import RUTA_CONFIG, cargar_configuracion, validar_configuracion


def _decimal(valor) -> Decimal:
    return Decimal(str(valor))


def _soles(valor) -> str:
    """El JSON conserva dinero como texto con dos decimales, sin errores de float."""
    return format(_decimal(valor), ".2f")


# Vocabulario acotado y revisable. No infiere equivalencia semántica general.
STOPWORDS = {"de", "para", "el", "la", "los", "las", "en", "y", "del",
             "adquisicion", "compra", "suministro", "con", "un", "una"}
SINONIMOS = {"laptop": ("computadora", "portatil"),
             "laptops": ("computadora", "portatil"),
             "computadoras": ("computadora",), "portatiles": ("portatil",)}


def _tokens_objeto(objeto: str) -> frozenset[str]:
    texto = "".join(c for c in unicodedata.normalize("NFKD", objeto.casefold())
                    if not unicodedata.combining(c))
    palabras = re.findall(r"[a-z0-9]+", texto)
    tokens = set()
    for palabra in palabras:
        if palabra not in STOPWORDS:
            tokens.update(SINONIMOS.get(palabra, (palabra,)))
    # Especificaciones de CPU no cambian la familia del portátil en esta demo.
    # Otros términos (mantenimiento, alquiler, reparación) SI se conservan.
    if {"computadora", "portatil"}.issubset(tokens):
        tokens = {t for t in tokens if t not in {"intel", "amd", "core"}
                  and not re.fullmatch(r"[ir][3579]", t)}
    return frozenset(tokens)


def _objeto_normalizado(objeto: str) -> str:
    tokens = _tokens_objeto(objeto)
    if tokens:
        return " ".join(sorted(tokens))
    # No agrupar objetos vacíos de contenido por haber eliminado stopwords.
    return "literal:" + " ".join(objeto.casefold().split())


def _hallazgo(contrato, regla_id, regla, evidencia) -> dict:
    return {
        "contratacion_id": contrato["id"],
        "codigo": contrato["codigo"],
        "regla_id": regla_id,
        "nombre": regla["nombre"],
        "severidad": regla["severidad"],
        "base_legal": regla["base_legal"],
        "evidencia_json": {
            **evidencia,
            "parametros_aplicados": deepcopy(regla["parametros"]),
        },
    }


def regla_fraccionamiento(contrataciones, pagos, config) -> list[dict]:
    """R01: contratos menores al umbral cuya suma lo alcanza en una ventana real."""
    regla_id = "R01_FRACCIONAMIENTO"
    regla = config["reglas"][regla_id]
    if not regla["activa"]:
        return []
    p = regla["parametros"]
    umbral = _decimal(p["umbral_monto"])
    grupos = defaultdict(list)
    for contrato in contrataciones:
        if _decimal(contrato["monto"]) < umbral:
            clave = (contrato["entidad_id"], contrato["proveedor_id"], _objeto_normalizado(contrato["objeto"]))
            grupos[clave].append(contrato)
    encontrados = {}
    for clave, grupo in sorted(grupos.items()):
        grupo = sorted(grupo, key=lambda c: (c["fecha"], c["id"]))
        fin = 0
        total = Decimal("0")
        asignados_hasta = 0
        for inicio, primero in enumerate(grupo):
            dias_disponibles = (date.max - primero["fecha"]).days
            limite = primero["fecha"] + timedelta(days=min(p["ventana_dias"], dias_disponibles))
            while fin < len(grupo) and grupo[fin]["fecha"] <= limite:
                total += _decimal(grupo[fin]["monto"])
                fin += 1
            if fin - inicio >= p["minimo_contratos"] and total >= umbral and fin > asignados_hasta:
                ventana = grupo[inicio:fin]
                evidencia = {
                    "entidad_id": clave[0], "proveedor_id": clave[1], "objeto_normalizado": clave[2],
                    "metodo_agrupacion": "Tokens canónicos con vocabulario controlado, no similitud semántica general",
                    "objetos_originales": sorted({c["objeto"] for c in ventana}),
                    "fecha_inicio": primero["fecha"].isoformat(),
                    "fecha_fin_ventana": limite.isoformat(),
                    "ultima_fecha_observada": ventana[-1]["fecha"].isoformat(),
                    "cantidad_contratos": len(ventana), "monto_acumulado": _soles(total),
                    "contratos": [{"id": c["id"], "codigo": c["codigo"],
                        "fecha": c["fecha"].isoformat(), "monto": _soles(c["monto"]),
                        "objeto": c["objeto"]} for c in ventana],
                    "criterio": "Misma entidad/proveedor y tokens canónicos; cada monto < umbral; suma >= umbral; ventana inclusiva.",
                }
                for posicion in range(max(inicio, asignados_hasta), fin):
                    contrato = grupo[posicion]
                    encontrados[contrato["id"]] = _hallazgo(contrato, regla_id, regla, deepcopy(evidencia))
                asignados_hasta = fin
            total -= _decimal(primero["monto"])
    return [encontrados[clave] for clave in sorted(encontrados)]


def regla_proveedor_dominante(contrataciones, pagos, config) -> list[dict]:
    """R02: participación por cantidad en una entidad y año calendario completo."""
    regla_id = "R02_PROVEEDOR_DOMINANTE"
    regla = config["reglas"][regla_id]
    if not regla["activa"]:
        return []
    p = regla["parametros"]
    periodos = defaultdict(list)
    for contrato in contrataciones:
        periodos[(contrato["entidad_id"], contrato["fecha"].year)].append(contrato)
    hallazgos = []
    for (entidad_id, anio), universo in sorted(periodos.items()):
        if len(universo) < p["minimo_contratos_entidad"]:
            continue
        proveedores = defaultdict(list)
        for contrato in sorted(universo, key=lambda c: c["id"]):
            proveedores[contrato["proveedor_id"]].append(contrato)
        for proveedor_id, contratos in sorted(proveedores.items()):
            proporcion = Decimal(len(contratos)) / Decimal(len(universo))
            if len(contratos) < p["minimo_contratos_proveedor"] or proporcion < _decimal(p["proporcion_minima"]):
                continue
            evidencia = {
                "entidad_id": entidad_id, "proveedor_id": proveedor_id, "anio": anio,
                "cantidad_entidad": len(universo), "cantidad_proveedor": len(contratos),
                "proporcion_observada": round(float(proporcion), 6),
                "contrataciones_entidad": sorted(c["id"] for c in universo),
                "contrataciones_proveedor": [c["id"] for c in contratos],
                "criterio": "Participación por cantidad >= proporción mínima y se cumplen ambos mínimos de contratos.",
                "alcance": "Análisis retrospectivo del conjunto suministrado, agrupado por entidad y año calendario.",
            }
            hallazgos.extend(_hallazgo(c, regla_id, regla, deepcopy(evidencia)) for c in contratos)
    return hallazgos


def regla_pagos_sin_sustento(contrataciones, pagos, config) -> list[dict]:
    """R03: uno o más pagos carecen de documentos exigidos por la configuración."""
    regla_id = "R03_PAGOS_SIN_SUSTENTO"
    regla = config["reglas"][regla_id]
    if not regla["activa"]:
        return []
    p = regla["parametros"]
    afectados = defaultdict(list)
    for pago in sorted(pagos, key=lambda pago: pago["id"]):
        faltantes = []
        if p["exigir_conformidad"] and not pago["tiene_conformidad"]:
            faltantes.append("conformidad")
        if p["exigir_comprobante"] and not pago["tiene_comprobante"]:
            faltantes.append("comprobante")
        if faltantes:
            afectados[pago["contratacion_id"]].append({
                "pago_id": pago["id"], "monto": _soles(pago["monto"]),
                "fecha_pago": pago["fecha_pago"].isoformat(),
                "tiene_conformidad": pago["tiene_conformidad"],
                "tiene_comprobante": pago["tiene_comprobante"], "documentos_faltantes": faltantes,
            })
    return [
        _hallazgo(c, regla_id, regla, {
            "pagos_sin_sustento": afectados[c["id"]],
            "cantidad_pagos_afectados": len(afectados[c["id"]]),
            "criterio": "Al menos un pago carece de uno o más documentos exigidos.",
        })
        for c in sorted(contrataciones, key=lambda c: c["id"]) if c["id"] in afectados
    ]


def regla_monto_cercano_umbral(contrataciones, pagos, config) -> list[dict]:
    """R04: límite inferior inclusivo, umbral superior exclusivo."""
    regla_id = "R04_MONTO_CERCANO_UMBRAL"
    regla = config["reglas"][regla_id]
    if not regla["activa"]:
        return []
    p = regla["parametros"]
    umbral = _decimal(p["umbral_monto"])
    inferior = umbral * _decimal(p["proporcion_inferior"])
    hallazgos = []
    for c in sorted(contrataciones, key=lambda c: c["id"]):
        monto = _decimal(c["monto"])
        if inferior <= monto < umbral:
            hallazgos.append(_hallazgo(c, regla_id, regla, {
                "monto": _soles(monto), "limite_inferior": str(inferior),
                "umbral_monto": _soles(umbral), "distancia_al_umbral": _soles(umbral - monto),
                "criterio": "umbral × proporción inferior <= monto < umbral; referencia didáctica, no legal.",
            }))
    return hallazgos


def regla_fechas_incoherentes(contrataciones, pagos, config) -> list[dict]:
    """R05: pago anterior al contrato o contrato anterior a la constitución."""
    regla_id = "R05_FECHAS_INCOHERENTES"
    regla = config["reglas"][regla_id]
    if not regla["activa"]:
        return []
    tolerancia = regla["parametros"]["tolerancia_dias"]
    pagos_por_contrato = defaultdict(list)
    for pago in sorted(pagos, key=lambda pago: pago["id"]):
        pagos_por_contrato[pago["contratacion_id"]].append(pago)
    hallazgos = []
    for c in sorted(contrataciones, key=lambda c: c["id"]):
        inconsistencias = []
        dias = (c["fecha_constitucion"] - c["fecha"]).days
        if dias > tolerancia:
            inconsistencias.append({
                "tipo": "contrato_anterior_a_constitucion", "dias_anticipacion": dias,
                "fecha_contrato": c["fecha"].isoformat(),
                "fecha_constitucion": c["fecha_constitucion"].isoformat(),
                "proveedor_id": c["proveedor_id"],
            })
        for pago in pagos_por_contrato[c["id"]]:
            dias = (c["fecha"] - pago["fecha_pago"]).days
            if dias > tolerancia:
                inconsistencias.append({
                    "tipo": "pago_anterior_al_contrato", "pago_id": pago["id"],
                    "dias_anticipacion": dias, "fecha_contrato": c["fecha"].isoformat(),
                    "fecha_pago": pago["fecha_pago"].isoformat(),
                })
        if inconsistencias:
            hallazgos.append(_hallazgo(c, regla_id, regla, {
                "inconsistencias": inconsistencias,
                "criterio": "Días de anticipación > tolerancia; igualdad de fechas permitida.",
            }))
    return hallazgos


def regla_proveedor_reciente(contrataciones, pagos, config) -> list[dict]:
    """R06: antigüedad válida no mayor al máximo y monto al menos igual al mínimo."""
    regla_id = "R06_PROVEEDOR_RECIENTE"
    regla = config["reglas"][regla_id]
    if not regla["activa"]:
        return []
    p = regla["parametros"]
    hallazgos = []
    for c in sorted(contrataciones, key=lambda c: c["id"]):
        antiguedad = (c["fecha"] - c["fecha_constitucion"]).days
        if 0 <= antiguedad <= p["antiguedad_maxima_dias"] and _decimal(c["monto"]) >= _decimal(p["monto_minimo"]):
            hallazgos.append(_hallazgo(c, regla_id, regla, {
                "proveedor_id": c["proveedor_id"], "fecha_contrato": c["fecha"].isoformat(),
                "fecha_constitucion": c["fecha_constitucion"].isoformat(),
                "antiguedad_dias": antiguedad, "monto": _soles(c["monto"]),
                "criterio": "0 <= antigüedad <= máximo; monto >= mínimo. Las antigüedades negativas se revisan en R05.",
            }))
    return hallazgos


FUNCIONES_REGLAS = (
    regla_fraccionamiento, regla_proveedor_dominante, regla_pagos_sin_sustento,
    regla_monto_cercano_umbral, regla_fechas_incoherentes, regla_proveedor_reciente,
)


def _validar_datos(contrataciones, pagos) -> None:
    """No interpretar datos ausentes como expedientes sin hallazgos."""
    ids_contratos = set()
    ids_pagos = set()
    for filas, campos, ids in (
        (contrataciones, ("id", "codigo", "entidad_id", "proveedor_id", "objeto", "monto", "fecha", "fecha_constitucion"), ids_contratos),
        (pagos, ("id", "contratacion_id", "monto", "fecha_pago", "tiene_conformidad", "tiene_comprobante"), ids_pagos),
    ):
        for fila in filas:
            if not isinstance(fila, dict) or any(campo not in fila or fila[campo] is None for campo in campos):
                raise ValueError(f"Registro incompleto. Campos obligatorios: {', '.join(campos)}")
            if type(fila["id"]) is not int or fila["id"] <= 0 or fila["id"] in ids:
                raise ValueError("Los identificadores deben ser enteros positivos y únicos en cada tabla.")
            ids.add(fila["id"])
            try:
                monto = _decimal(fila["monto"])
                if not monto.is_finite() or monto <= 0:
                    raise ValueError("Cada monto debe ser positivo y finito.")
            except InvalidOperation as error:
                raise ValueError("Monto no numérico.") from error
            for campo in ("fecha", "fecha_constitucion", "fecha_pago"):
                if campo in campos and type(fila[campo]) is not date:
                    raise ValueError(f"{campo} debe ser datetime.date, como lo entrega la consulta SQLAlchemy.")
    for c in contrataciones:
        if not isinstance(c["objeto"], str) or not c["objeto"].strip():
            raise ValueError("El objeto debe ser texto no vacío.")
        if any(type(c[campo]) is not int or c[campo] <= 0 for campo in ("entidad_id", "proveedor_id")):
            raise ValueError("Entidad y proveedor deben tener identificadores enteros positivos.")
    for pago in pagos:
        if type(pago["contratacion_id"]) is not int or pago["contratacion_id"] not in ids_contratos:
            raise ValueError("Hay un pago cuya contratación no está en el conjunto suministrado.")
        if any(type(pago[campo]) is not bool for campo in ("tiene_conformidad", "tiene_comprobante")):
            raise ValueError("Los indicadores de sustento deben ser booleanos.")


def evaluar_reglas(contrataciones: list[dict], pagos: list[dict], config: dict | None = None) -> list[dict]:
    """Evalúa el conjunto completo antes de aplicar filtros de visualización.

    Devuelve como máximo un hallazgo por contratación y regla. Una contratación
    sí puede activar varias reglas. La salida es JSON serializable y determinista.
    """
    if config is None:
        config = cargar_configuracion()
    validar_configuracion(config)
    _validar_datos(contrataciones, pagos)
    hallazgos = []
    for funcion in FUNCIONES_REGLAS:
        hallazgos.extend(funcion(contrataciones, pagos, config))
    return sorted(hallazgos, key=lambda h: (h["contratacion_id"], h["regla_id"]))


def main() -> None:
    # Importaciones locales: las seis funciones no necesitan una sesión de BD.
    from db.database import (
        RUTA_BD, consultar_contrataciones, consultar_pagos, crear_motor, obtener_sesion,
    )

    parser = argparse.ArgumentParser(description="Evaluar las seis reglas sobre SQLite, sin guardar alertas.")
    parser.add_argument("--bd", type=Path, default=RUTA_BD)
    parser.add_argument("--config", type=Path, default=RUTA_CONFIG)
    parser.add_argument("--salida", type=Path, default=RUTA_BD.parent / "hallazgos_reglas.json")
    args = parser.parse_args()
    if not args.bd.is_file():
        parser.error("No existe la base. Ejecuta primero: python -m db.seed")
    salida = args.salida.resolve()
    if salida.suffix.lower() != ".json" or salida in (args.bd.resolve(), args.config.resolve()):
        parser.error("La salida debe ser un archivo .json distinto de la base y la configuración.")
    motor = crear_motor(args.bd)
    try:
        config = cargar_configuracion(args.config)
        with obtener_sesion(motor) as sesion:
            contratos = consultar_contrataciones(sesion)
            pagos = consultar_pagos(sesion)
        hallazgos = evaluar_reglas(contratos, pagos, config)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    finally:
        motor.dispose()
    resumen = {
        "contrataciones_evaluadas": len(contratos), "pagos_evaluados": len(pagos),
        "hallazgos": len(hallazgos),
        "contrataciones_con_hallazgos": len({h["contratacion_id"] for h in hallazgos}),
        "por_regla": {regla_id: 0 for regla_id in config["reglas"]},
    }
    resumen["por_regla"].update(Counter(h["regla_id"] for h in hallazgos))
    informe = {
        "aviso": "Datos sintéticos. Los hallazgos requieren revisión humana y no constituyen acusaciones.",
        "configuracion_aplicada": config, "resumen": resumen, "hallazgos": hallazgos,
    }
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    print("Evidencias:", salida)
    print("La base de datos no fue modificada; persistencia de alertas e integración: Fase 4.")


if __name__ == "__main__":
    main()
