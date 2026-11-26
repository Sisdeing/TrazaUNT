"""Isolation Forest aporta una señal de rareza; no crea ni decide alertas.

Se ajusta y evalúa sobre el mismo conjunto completo de datos, de forma
retrospectiva y no supervisada. La rareza no es una probabilidad de irregularidad
ni una evaluación de desempeño sobre datos nuevos. No se utiliza ground truth.
"""

from collections import Counter, defaultdict
from datetime import date
import math

import pandas as pd

VARIABLES = ["monto", "frecuencia_proveedor", "concentracion_entidad",
             "ratio_monto_promedio", "dias_desde_constitucion", "n_postores"]


def preparar_variables(contrataciones: list[dict]) -> pd.DataFrame:
    """Selecciona seis variables; los IDs quedan fuera de las columnas.

    Frecuencia: contratos de cada proveedor por año, considerando todas las
    entidades. Concentración: HHI por entidad y año, calculado con las cuotas
    de contratos de cada proveedor. Un HHI de 1 indica un único proveedor.
    """
    campos = ("id", "entidad_id", "proveedor_id", "fecha", "monto", "objeto", "fecha_constitucion", "n_postores")
    registros = []
    identificadores = set()
    for contrato in contrataciones:
        if not isinstance(contrato, dict) or any(campo not in contrato for campo in campos):
            raise ValueError(f"La IA requiere estos campos: {', '.join(campos)}.")
        for campo in ("id", "entidad_id", "proveedor_id"):
            if type(contrato[campo]) is not int or contrato[campo] <= 0:
                raise ValueError(f"{campo} debe ser un entero positivo.")
        if contrato["id"] in identificadores:
            raise ValueError("No se admiten IDs de contratación duplicados.")
        identificadores.add(contrato["id"])
        if type(contrato["fecha"]) is not date:
            raise ValueError("fecha debe ser datetime.date, como en la consulta SQLAlchemy.")
        if type(contrato["fecha_constitucion"]) is not date:
            raise ValueError("fecha_constitucion debe ser datetime.date.")
        if type(contrato["n_postores"]) is not int or contrato["n_postores"] < 1:
            raise ValueError("n_postores debe ser entero positivo.")
        if not isinstance(contrato["objeto"], str) or not contrato["objeto"].strip():
            raise ValueError("objeto debe ser texto no vacío.")
        try:
            monto = float(contrato["monto"])
        except (ValueError, TypeError, OverflowError) as error:
            raise ValueError("El monto debe ser numérico, positivo y finito.") from error
        if isinstance(contrato["monto"], bool) or not math.isfinite(monto) or monto <= 0:
            raise ValueError("El monto debe ser numérico, positivo y finito.")
        # Selección explícita: no se copian etiquetas, códigos ni nombres de personas.
        # El objeto solo define el grupo de referencia, nunca entra como texto al modelo.
        registros.append({
            "id": contrato["id"], "entidad_id": contrato["entidad_id"],
            "proveedor_id": contrato["proveedor_id"], "anio": contrato["fecha"].year,
            "monto": monto, "objeto": contrato["objeto"],
            "dias_desde_constitucion": (contrato["fecha"] - contrato["fecha_constitucion"]).days,
            "n_postores": contrato["n_postores"],
        })
    registros.sort(key=lambda contrato: contrato["id"])
    frecuencia = Counter((c["proveedor_id"], c["anio"]) for c in registros)
    totales = Counter((c["entidad_id"], c["anio"]) for c in registros)
    adjudicaciones = Counter((c["entidad_id"], c["anio"], c["proveedor_id"]) for c in registros)
    concentracion = defaultdict(float)
    for (entidad, anio, proveedor), cantidad in sorted(adjudicaciones.items()):
        concentracion[(entidad, anio)] += (cantidad / totales[(entidad, anio)]) ** 2

    from services.reglas import _objeto_normalizado
    sumas, cantidades = defaultdict(float), Counter()
    for c in registros:
        clave = (_objeto_normalizado(c["objeto"]), c["anio"])
        sumas[clave] += c["monto"]
        cantidades[clave] += 1
    filas = []
    for c in registros:
        clave = (_objeto_normalizado(c["objeto"]), c["anio"])
        promedio = sumas[clave] / cantidades[clave]
        filas.append({
            "monto": c["monto"],
            "ratio_monto_promedio": c["monto"] / promedio,
            "dias_desde_constitucion": c["dias_desde_constitucion"],
            "n_postores": c["n_postores"],
            "frecuencia_proveedor": frecuencia[(c["proveedor_id"], c["anio"])],
            "concentracion_entidad": concentracion[(c["entidad_id"], c["anio"])],
        })
    indice = pd.Index([c["id"] for c in registros], name="contratacion_id", dtype="int64")
    return pd.DataFrame(filas, index=indice, columns=VARIABLES)


def _parametros_ia(config: dict) -> dict:
    """Valida esta sección también cuando el módulo se usa de forma aislada."""
    parametros = config.get("ia") if isinstance(config, dict) else None
    if not isinstance(parametros, dict):
        raise ValueError("Falta la sección ia de la configuración de Fase 3.")
    if type(parametros.get("activa")) is not bool:
        raise ValueError("ia.activa debe ser true o false.")
    for campo, minimo in (("semilla", 0), ("n_estimadores", 1), ("max_muestras", 2), ("minimo_registros", 2)):
        if type(parametros.get(campo)) is not int or parametros[campo] < minimo:
            raise ValueError(f"ia.{campo} debe ser un entero mayor o igual a {minimo}.")
    if parametros["semilla"] > 2**32 - 1:
        raise ValueError("ia.semilla debe ser como máximo 4294967295.")
    return parametros


def evaluar_anomalias(contrataciones: list[dict], config: dict) -> dict[int, dict]:
    """Devuelve una señal por contratación, nunca una decisión de alerta.

    Índice de aislamiento = -score_samples. Rareza didáctica fija:
    max(0, min(1, 2 * (índice - 0.5))). No es un percentil ni usa etiquetas.
    Una entrada sin variación o insuficiente conserva las reglas sin aporte IA.
    """
    p = _parametros_ia(config)
    variables = preparar_variables(contrataciones)
    if variables.empty:
        return {}
    motivo = ""
    if not p["activa"]:
        motivo = "IA desactivada en la configuración."
    elif len(variables) < p["minimo_registros"]:
        motivo = f"Solo hay {len(variables)} registros; se requieren al menos {p['minimo_registros']}."
    elif (variables.nunique(dropna=False) <= 1).all():
        motivo = "Las variables son idénticas en todos los registros; no hay variación para evaluar."

    indices = None
    if not motivo:
        # Importación local: las reglas pueden continuar cuando la IA está apagada.
        from sklearn.ensemble import IsolationForest

        modelo = IsolationForest(
            n_estimators=p["n_estimadores"], max_samples=min(p["max_muestras"], len(variables)),
            contamination="auto", random_state=p["semilla"], n_jobs=1,
        )
        # La selección evita entrenar con el índice/ID de la contratación.
        matriz = variables[VARIABLES]
        modelo.fit(matriz)
        indices = -modelo.score_samples(matriz)

    resultado = {}
    for posicion, (contratacion_id, fila) in enumerate(variables.iterrows()):
        indice = float(indices[posicion]) if indices is not None else None
        rareza = max(0.0, min(1.0, 2 * (indice - 0.5))) if indice is not None else 0.0
        resultado[int(contratacion_id)] = {
            "contratacion_id": int(contratacion_id), "disponible": indices is not None,
            "rareza": rareza, "indice_aislamiento": indice,
            "motivo": motivo or "Señal retrospectiva de Isolation Forest; no determina irregularidad ni genera alertas.",
            "variables": {nombre: float(fila[nombre]) for nombre in VARIABLES},
        }
    return resultado
