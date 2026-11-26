"""Priorización transparente: las reglas predominan y la IA no crea alertas.

Ejecutar el análisis completo: python -m services.scoring
La salida es un informe JSON; la persistencia de alertas corresponde a Fase 4.
"""

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import json
import math
from pathlib import Path

from services.configuracion import RUTA_CONFIG, cargar_configuracion, validar_configuracion


def calcular_score(hallazgos: list[dict], senal_ia: dict, config: dict) -> dict:
    """Score = peso_reglas × min(1, suma de intensidades) + peso_ia × rareza.

    Solo se suma una vez cada regla. Un hallazgo requiere revisión incluso
    cuando su prioridad es verde. La rareza sola nunca genera esa obligación.
    """
    validar_configuracion(config)
    p = config["scoring"]
    if type(senal_ia.get("disponible")) is not bool:
        raise ValueError("La señal de IA debe indicar si está disponible.")
    if not config["ia"]["activa"] and senal_ia["disponible"]:
        raise ValueError("La IA está desactivada, pero se recibió una señal disponible.")
    rareza = senal_ia.get("rareza")
    if type(rareza) not in (int, float) or not 0 <= rareza <= 1:
        raise ValueError("La rareza debe ser un número finito entre 0 y 1.")
    if not senal_ia["disponible"] and rareza != 0:
        raise ValueError("Una señal no disponible debe tener rareza igual a cero.")

    reglas_unicas = {}
    contrataciones = set()
    for h in hallazgos:
        regla_id = h["regla_id"]
        severidad = h["severidad"]
        if regla_id not in config["reglas"] or severidad not in p["intensidad_por_severidad"]:
            raise ValueError("Hallazgo con regla o severidad desconocida.")
        if regla_id in reglas_unicas and reglas_unicas[regla_id] != severidad:
            raise ValueError("Una misma regla no puede tener dos severidades en el mismo cálculo.")
        reglas_unicas[regla_id] = severidad
        contrataciones.add(h["contratacion_id"])
    if len(contrataciones) > 1:
        raise ValueError("calcular_score recibe hallazgos de una sola contratación.")
    if contrataciones and senal_ia.get("contratacion_id") not in contrataciones:
        raise ValueError("La señal de IA y los hallazgos pertenecen a contrataciones distintas.")

    intensidad = min(1.0, math.fsum(
        p["intensidad_por_severidad"][reglas_unicas[regla_id]] for regla_id in sorted(reglas_unicas)
    ))
    # Redondear los aportes primero permite reconstruir exactamente el score mostrado.
    aporte_reglas = round(p["peso_reglas"] * intensidad, 2)
    aporte_ia = round(p["peso_ia"] * rareza, 2)
    score = round(min(100.0, max(0.0, aporte_reglas + aporte_ia)), 2)
    semaforo = "rojo" if score >= p["rojo_desde"] else "amarillo" if score >= p["amarillo_desde"] else "verde"
    return {
        "score": score, "semaforo": semaforo,
        "requiere_revision": bool(reglas_unicas), "numero_reglas": len(reglas_unicas),
        "aportes": {"reglas": aporte_reglas, "ia": aporte_ia},
        "intensidad_reglas": intensidad, "rareza_ia": rareza,
        "reglas_activadas": sorted(reglas_unicas),
    }


def evaluar_expedientes(contrataciones: list[dict], pagos: list[dict], config: dict | None = None) -> list[dict]:
    """Ejecuta reglas, rareza, score y plantillas sobre el conjunto completo.

    Entrenamiento y evaluación son retrospectivos sobre la misma muestra. No se
    consumen etiquetas ni se presenta esta ejecución como validación predictiva.
    Claude no se invoca aquí, aunque alguien lo habilite en la configuración.
    """
    from services.anomalias import evaluar_anomalias
    from services.explicador import explicar_hallazgo, explicar_resultado
    from services.reglas import evaluar_reglas

    if config is None:
        config = cargar_configuracion()
    validar_configuracion(config)
    hallazgos = evaluar_reglas(contrataciones, pagos, config)
    senales = evaluar_anomalias(contrataciones, config)
    por_contrato = defaultdict(list)
    for hallazgo in hallazgos:
        copia = deepcopy(hallazgo)
        copia["explicacion"] = explicar_hallazgo(copia)
        por_contrato[copia["contratacion_id"]].append(copia)

    resultados = []
    for contrato in sorted(contrataciones, key=lambda c: c["id"]):
        encontrados = por_contrato[contrato["id"]]
        senal = senales[contrato["id"]]
        resultado = {
            "contratacion_id": contrato["id"], "codigo": contrato["codigo"],
            "hallazgos": encontrados, "ia": senal,
            "priorizacion": calcular_score(encontrados, senal, config),
        }
        resultado["explicacion"] = explicar_resultado(resultado)
        resultados.append(resultado)
    return resultados


def main() -> None:
    from db.database import (
        RUTA_BD, consultar_contrataciones, consultar_pagos, crear_motor, obtener_sesion,
    )
    import sklearn
    from services.anomalias import VARIABLES

    parser = argparse.ArgumentParser(description="Analizar reglas, rareza, score y explicaciones sin modificar SQLite.")
    parser.add_argument("--bd", type=Path, default=RUTA_BD)
    parser.add_argument("--config", type=Path, default=RUTA_CONFIG)
    parser.add_argument("--salida", type=Path, default=RUTA_BD.parent / "analisis_expedientes.json")
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
        resultados = evaluar_expedientes(contratos, pagos, config)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    finally:
        motor.dispose()

    colores = {"verde": 0, "amarillo": 0, "rojo": 0}
    colores.update(Counter(r["priorizacion"]["semaforo"] for r in resultados))
    resumen = {
        "contrataciones_evaluadas": len(resultados),
        "hallazgos_de_reglas": sum(len(r["hallazgos"]) for r in resultados),
        "contrataciones_para_revision": sum(r["priorizacion"]["requiere_revision"] for r in resultados),
        "senales_ia_disponibles": sum(r["ia"]["disponible"] for r in resultados),
        "semaforos": colores,
    }
    informe = {
        "aviso": "Datos sintéticos. El score prioriza revisión; no mide probabilidad de corrupción.",
        "configuracion_aplicada": config,
        "metodo_ia": {
            "algoritmo": "IsolationForest", "version_sklearn": sklearn.__version__,
            "variables": VARIABLES,
            "rareza": "clip(2 * (-score_samples - 0.5), 0, 1)",
            "alcance": "Entrenamiento y evaluación retrospectivos sobre la misma muestra, sin ground truth.",
        },
        "claude_invocado": False, "resumen": resumen, "resultados": resultados,
    }
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    print("Informe con explicaciones:", salida)
    print("SQLite no fue modificado y Claude no fue invocado. Integración con la interfaz: Fase 4.")


if __name__ == "__main__":
    main()
