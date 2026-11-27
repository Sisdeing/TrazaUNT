"""Lectura y validación del YAML, sin ejecutar objetos Python del archivo."""

import math
from datetime import date
from decimal import Decimal
from pathlib import Path

import yaml

RUTA_CONFIG = Path(__file__).resolve().parents[1] / "config" / "reglas.yaml"

# Tipo, mínimo y máximo permitido. None significa que no hay cota superior.
PARAMETROS = {
    "R01_FRACCIONAMIENTO": {
        "ventana_dias": (int, 0, 3650),
        "minimo_contratos": (int, 2, None),
        "umbral_uit": (float, 0, None),
        "valor_uit": (float, 0, None),
    },
    "R02_PROVEEDOR_DOMINANTE": {
        "minimo_contratos_entidad": (int, 1, None),
        "minimo_contratos_proveedor": (int, 1, None),
        "proporcion_minima": (float, 0, 1),
    },
    "R03_PAGOS_SIN_SUSTENTO": {
        "exigir_conformidad": (bool, None, None),
        "exigir_comprobante": (bool, None, None),
    },
    "R04_MONTO_CERCANO_UMBRAL": {
        "umbral_uit": (float, 0, None),
        "valor_uit": (float, 0, None),
        "proporcion_inferior": (float, 0, 1),
    },
    "R05_FECHAS_INCOHERENTES": {"tolerancia_dias": (int, 0, None)},
    "R06_PROVEEDOR_RECIENTE": {
        "antiguedad_maxima_dias": (int, 0, None),
        "monto_minimo": (float, 0, None),
    },
}


# Reglas cuyo umbral se expresa en UIT (p. ej. 8 UIT); el monto en soles se calcula al cargar.
REGLAS_UIT = ("R01_FRACCIONAMIENTO", "R04_MONTO_CERCANO_UMBRAL")


def _monto_uit(parametros):
    return round(float(parametros["umbral_uit"]) * float(parametros["valor_uit"]), 2)


class _CargadorSeguro(yaml.SafeLoader):
    """SafeLoader con rechazo de claves repetidas para evitar errores silenciosos."""


def _leer_mapa(cargador, nodo):
    resultado = {}
    for clave_nodo, valor_nodo in nodo.value:
        clave = cargador.construct_object(clave_nodo)
        if not isinstance(clave, str) or clave in resultado:
            raise ValueError(f"Clave YAML no textual o repetida: {clave!r}")
        resultado[clave] = cargador.construct_object(valor_nodo)
    return resultado


_CargadorSeguro.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _leer_mapa)


def _exigir_claves(valor, esperadas, ruta):
    if not isinstance(valor, dict) or set(valor) != set(esperadas):
        raise ValueError(f"{ruta}: se requieren exactamente estas claves: {', '.join(esperadas)}")


def validar_configuracion(config: dict) -> None:
    """Rechaza errores de nombres, tipos y rangos antes de ejecutar las reglas."""
    _exigir_claves(config, ("version", "reglas", "ia", "scoring", "claude"), "configuración")
    if type(config["version"]) is not int or config["version"] != 2:
        raise ValueError("La versión debe ser 2; utiliza el YAML completo de Fase 3.")
    _exigir_claves(config["reglas"], PARAMETROS, "reglas")
    for regla_id, especificaciones in PARAMETROS.items():
        regla = config["reglas"][regla_id]
        _exigir_claves(regla, ("nombre", "activa", "severidad", "base_legal", "parametros"), regla_id)
        for campo in ("nombre", "base_legal"):
            if not isinstance(regla[campo], str) or not regla[campo].strip():
                raise ValueError(f"{regla_id}.{campo}: debe ser texto no vacío.")
        if type(regla["activa"]) is not bool:
            raise ValueError(f"{regla_id}.activa: usa true o false, sin comillas.")
        if regla["severidad"] not in ("baja", "media", "alta"):
            raise ValueError(f"{regla_id}.severidad: usa baja, media o alta.")
        # «umbral_monto» no se escribe en el YAML: se deriva de umbral_uit × valor_uit al cargar.
        derivada = set(especificaciones) | ({"umbral_monto"} & set(regla["parametros"]) if regla_id in REGLAS_UIT else set())
        _exigir_claves(regla["parametros"], derivada, f"{regla_id}.parametros")
        for nombre, (tipo, minimo, maximo) in especificaciones.items():
            valor = regla["parametros"][nombre]
            ruta = f"{regla_id}.{nombre}"
            if tipo is bool:
                if type(valor) is not bool:
                    raise ValueError(f"{ruta}: usa true o false, sin comillas.")
                continue
            if tipo is int:
                if type(valor) is not int or valor < minimo:
                    raise ValueError(f"{ruta}: debe ser un entero mayor o igual a {minimo}.")
                if maximo is not None and valor > maximo:
                    raise ValueError(f"{ruta}: debe ser como máximo {maximo}.")
            else:
                if type(valor) not in (int, float) or not math.isfinite(valor):
                    raise ValueError(f"{ruta}: debe ser un número finito.")
                if valor <= minimo or (maximo is not None and valor > maximo):
                    raise ValueError(f"{ruta}: debe ser mayor que {minimo} y como máximo {maximo or 'sin límite'}.")
        if regla_id in REGLAS_UIT and "umbral_monto" in regla["parametros"]:
            p = regla["parametros"]
            if abs(p["umbral_monto"] - _monto_uit(p)) > 0.005:
                raise ValueError(f"{regla_id}.umbral_monto no coincide con umbral_uit × valor_uit.")
        if regla_id == "R04_MONTO_CERCANO_UMBRAL" and regla["parametros"]["proporcion_inferior"] >= 1:
            raise ValueError("R04_MONTO_CERCANO_UMBRAL.proporcion_inferior debe ser menor que 1.")

    ia = config["ia"]
    _exigir_claves(ia, ("activa", "semilla", "n_estimadores", "max_muestras", "minimo_registros"), "ia")
    if type(ia["activa"]) is not bool:
        raise ValueError("ia.activa debe ser true o false.")
    for campo, minimo, maximo in (
        ("semilla", 0, 2**32 - 1), ("n_estimadores", 1, 2000),
        ("max_muestras", 2, 100000), ("minimo_registros", 2, 100000),
    ):
        if type(ia[campo]) is not int or not minimo <= ia[campo] <= maximo:
            raise ValueError(f"ia.{campo}: debe ser un entero entre {minimo} y {maximo}.")

    scoring = config["scoring"]
    _exigir_claves(scoring, ("peso_reglas", "peso_ia", "intensidad_por_severidad", "amarillo_desde", "rojo_desde"), "scoring")
    for campo in ("peso_reglas", "peso_ia", "amarillo_desde", "rojo_desde"):
        _numero_en_rango(scoring[campo], 0, 100, f"scoring.{campo}")
        valor_decimal = Decimal(str(scoring[campo]))
        if valor_decimal != valor_decimal.quantize(Decimal("0.01")):
            raise ValueError(f"scoring.{campo}: utiliza como máximo dos decimales.")
    if not math.isclose(scoring["peso_reglas"] + scoring["peso_ia"], 100, abs_tol=1e-9):
        raise ValueError("Los pesos de reglas e IA deben sumar 100.")
    if scoring["peso_reglas"] <= scoring["peso_ia"]:
        raise ValueError("Las reglas deben tener mayor peso que la IA.")
    if not scoring["peso_ia"] < scoring["amarillo_desde"] < scoring["rojo_desde"] <= 100:
        raise ValueError("Debe cumplirse: peso_ia < amarillo_desde < rojo_desde <= 100. La IA sola queda en verde.")
    intensidades = scoring["intensidad_por_severidad"]
    _exigir_claves(intensidades, ("baja", "media", "alta"), "intensidad_por_severidad")
    for severidad, valor in intensidades.items():
        _numero_en_rango(valor, 0, 1, f"intensidad_por_severidad.{severidad}")
    if not 0 < intensidades["baja"] <= intensidades["media"] <= intensidades["alta"]:
        raise ValueError("Las intensidades deben ser positivas y no disminuir de baja a alta.")

    claude = config["claude"]
    _exigir_claves(claude, ("habilitado", "modelo_env", "clave_env", "version_api", "max_tokens", "timeout_segundos"), "claude")
    if type(claude["habilitado"]) is not bool:
        raise ValueError("claude.habilitado debe ser true o false.")
    for campo in ("modelo_env", "clave_env", "version_api"):
        if not isinstance(claude[campo], str) or not claude[campo].strip():
            raise ValueError(f"claude.{campo} debe ser texto no vacío.")
    try:
        date.fromisoformat(claude["version_api"])
    except ValueError as error:
        raise ValueError("claude.version_api debe ser una fecha AAAA-MM-DD entre comillas.") from error
    if type(claude["max_tokens"]) is not int or not 1 <= claude["max_tokens"] <= 4096:
        raise ValueError("claude.max_tokens debe ser un entero entre 1 y 4096.")
    _numero_en_rango(claude["timeout_segundos"], 1, 60, "claude.timeout_segundos")


def _numero_en_rango(valor, minimo, maximo, nombre):
    """Rechaza también booleanos, NaN e infinitos en parámetros numéricos."""
    if type(valor) not in (int, float) or not minimo <= valor <= maximo:
        raise ValueError(f"{nombre} debe ser un número finito entre {minimo} y {maximo}.")


def cargar_configuracion(ruta: str | Path = RUTA_CONFIG) -> dict:
    """Lee el archivo en cada llamada; editarlo no requiere cambiar código Python."""
    try:
        contenido = Path(ruta).read_text(encoding="utf-8-sig")
        config = yaml.load(contenido, Loader=_CargadorSeguro)
    except yaml.YAMLError as error:
        raise ValueError(f"YAML inválido en {ruta}: {error}") from error
    validar_configuracion(config)
    for regla_id in REGLAS_UIT:
        p = config["reglas"][regla_id]["parametros"]
        p["umbral_monto"] = _monto_uit(p)
    return config
