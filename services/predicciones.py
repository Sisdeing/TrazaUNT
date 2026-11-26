"""Pronóstico experimental de mora para la siguiente cuota de una concesión demo."""

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from hashlib import sha256
import json
import random

import numpy as np
import sklearn
from fastapi import APIRouter, Request
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    select,
)

from db.database import obtener_sesion
from db.integridad import Abono, Concesion, Cuota
from db.models import Base
from services.integridad import CORTE

VERSION = "mora-cuota-1.0"
VARIABLES = [
    "Cuotas pendientes entre las tres últimas",
    "Demora media observada (días)",
    "Cuotas pagadas después del vencimiento",
]
router = APIRouter(prefix="/api", tags=["Predicción experimental"])


class Pronostico(Base):
    __tablename__ = "pronosticos_concesion"
    __table_args__ = (UniqueConstraint("concesion_id", "huella"),)
    id = Column(Integer, primary_key=True)
    concesion_id = Column(ForeignKey("concesiones.id"), nullable=False, index=True)
    corte = Column(Date, nullable=False)
    version = Column(String(60), nullable=False)
    huella = Column(String(64), nullable=False)
    datos = Column(JSON, nullable=False)
    creado = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )


def variables(cuotas, corte):
    """(Vencimiento, fecha de cobertura íntegra). Una fecha futura se trata como no observada."""
    anteriores = sorted((v, p) for v, p in cuotas if v <= corte)[-3:]
    if len(anteriores) < 3:
        return None
    abiertas = tardias = dias = 0
    for vence, pago in anteriores:
        observado = pago if pago is not None and pago <= corte else None
        abiertas += observado is None
        tardias += observado is not None and observado > vence
        dias += max(0, min(90, ((observado or corte) - vence).days))
    return [abiertas, round(dias / 3, 2), tardias]


def muestra():
    rng = random.Random(42)
    filas = []
    for empresa in range(48):
        cuotas = []
        propension = rng.uniform(0.08, 0.8)
        tension = False
        for t in range(72):
            y, m = 2020 + t // 12, 1 + t % 12
            vence = date(y, m, monthrange(y, m)[1])
            corte = date(y, m, 23)
            x = variables(cuotas, corte)
            if rng.random() < 0.18:
                tension = rng.random() < propension
            if tension:
                dias = (
                    rng.randint(20, 90) if rng.random() < 0.83 else rng.randint(0, 18)
                )
            else:
                dias = (
                    rng.randint(0, 10) if rng.random() < 0.90 else rng.randint(11, 46)
                )
            pago = vence + timedelta(days=dias)
            if x is not None:
                filas.append(
                    (corte, vence + timedelta(days=30), empresa, x, int(dias > 30))
                )
            cuotas.append((vence, pago))
    return filas


def metricas(y, p, umbral):
    estimado = p >= umbral
    return dict(
        precision=round(float(precision_score(y, estimado, zero_division=0)), 4),
        recall=round(float(recall_score(y, estimado, zero_division=0)), 4),
        f1=round(float(f1_score(y, estimado, zero_division=0)), 4),
        ap=round(float(average_precision_score(y, p)), 4),
        roc_auc=round(float(roc_auc_score(y, p)), 4),
        brier=round(float(brier_score_loss(y, p)), 4),
        matriz=confusion_matrix(y, estimado, labels=[0, 1]).tolist(),
    )


@lru_cache(maxsize=1)
def entrenar():
    registros = muestra()
    validacion = date(2024, 1, 1)
    prueba = date(2025, 1, 1)
    grupos = [
        [r for r in registros if r[1] < validacion],
        [r for r in registros if validacion <= r[0] and r[1] < prueba],
        [r for r in registros if prueba <= r[0]],
    ]
    (x, y), (xv, yv), (xt, yt) = [
        (np.array([r[3] for r in grupo]), np.array([r[4] for r in grupo]))
        for grupo in grupos
    ]
    modelos = {
        "Baseline": DummyClassifier(strategy="prior"),
        "Regresión logística": make_pipeline(
            StandardScaler(), LogisticRegression(random_state=42)
        ),
        "Random Forest": RandomForestClassifier(
            n_estimators=80, min_samples_leaf=18, max_depth=5, random_state=42, n_jobs=1
        ),
    }
    resultados = {}
    for nombre, modelo in modelos.items():
        modelo.fit(x, y)
        p = modelo.predict_proba(xv)[:, 1]
        umbral = float(
            max(
                np.arange(0.15, 0.86, 0.05),
                key=lambda t: f1_score(yv, p >= t, zero_division=0),
            )
        )
        resultados[nombre] = {
            "validacion": metricas(yv, p, umbral),
            "umbral": round(umbral, 2),
        }
    elegido = max(modelos, key=lambda n: resultados[n]["validacion"]["ap"])
    for n, modelo in modelos.items():
        resultados[n]["prueba"] = metricas(
            yt, modelo.predict_proba(xt)[:, 1], resultados[n]["umbral"]
        )
    apto = (
        elegido != "Baseline"
        and resultados[elegido]["prueba"]["ap"] > resultados["Baseline"]["prueba"]["ap"]
    )
    ficha = dict(
        version=VERSION,
        algoritmo=elegido,
        disponible=apto,
        semilla=42,
        sklearn=sklearn.__version__,
        evento="Siguiente cuota mensual con saldo pendiente a los 30 días del vencimiento",
        variables=VARIABLES,
        muestras=[len(g) for g in grupos],
        resultados=resultados,
        periodos=[
            [str(min(r[0] for r in g)), str(max(r[0] for r in g))] for g in grupos
        ],
        fuente="48 operadores ficticios con cuotas mensuales, 2020–2025; generador muestra().",
        limite="Predicción experimental entrenada con datos sintéticos. No validada para decisiones reales.",
    )
    return modelos[elegido], ficha


def evaluar(motor):
    modelo, registro = entrenar()
    with obtener_sesion(motor) as s:
        s.connection().exec_driver_sql("BEGIN IMMEDIATE")
        for c in s.scalars(select(Concesion)):
            cuotas = list(
                s.scalars(
                    select(Cuota)
                    .where(Cuota.concesion_id == c.id)
                    .order_by(Cuota.fecha)
                )
            )
            vencida = []
            for q in cuotas:
                if q.fecha > CORTE:
                    continue
                acumulado = 0
                fecha_pago = None
                for ab in s.scalars(
                    select(Abono)
                    .where(Abono.cuota_id == q.id, Abono.fecha <= CORTE)
                    .order_by(Abono.fecha, Abono.id)
                ):
                    acumulado += ab.monto
                    if acumulado >= q.exigible:
                        fecha_pago = ab.fecha
                        break
                vencida.append((q.fecha, fecha_pago))
            x = variables(vencida, CORTE)
            siguiente = next(
                (q for q in cuotas if CORTE < q.fecha <= CORTE + timedelta(days=31)),
                None,
            )
            datos = dict(
                variables=x,
                nivel="Predicción no disponible",
                horizonte=None,
                algoritmo=registro["algoritmo"],
                accion="Se requieren tres cuotas vencidas observables y un siguiente vencimiento a 31 días.",
            )
            if (
                x is not None
                and siguiente
                and registro["disponible"]
                and c.inicio <= CORTE <= c.fin
            ):
                umbral = registro["resultados"][registro["algoritmo"]]["umbral"]
                revisar = modelo.predict_proba([x])[0, 1] >= umbral
                datos.update(
                    nivel="Revisión prioritaria"
                    if revisar
                    else "Seguimiento ordinario",
                    horizonte=(siguiente.fecha + timedelta(days=30)).isoformat(),
                    accion="Contrastar calendario, abonos y saldo con el responsable de supervisión."
                    if revisar
                    else "Supervisar la próxima cuota en su fecha de vencimiento.",
                )
            huella = sha256(
                json.dumps([VERSION, CORTE.isoformat(), datos], sort_keys=True).encode()
            ).hexdigest()
            if not s.scalar(
                select(Pronostico.id).where(
                    Pronostico.concesion_id == c.id, Pronostico.huella == huella
                )
            ):
                s.add(
                    Pronostico(
                        concesion_id=c.id,
                        corte=CORTE,
                        version=VERSION,
                        huella=huella,
                        datos=datos,
                    )
                )


@router.get("/modelos")
def modelos():
    return entrenar()[1]


@router.get("/predicciones")
def pronosticos(request: Request):
    with obtener_sesion(request.app.state.motor) as s:
        ultimos = {}
        for fila, c in s.execute(
            select(Pronostico, Concesion).join(Concesion).order_by(Pronostico.id.desc())
        ):
            ultimos.setdefault(
                c.id,
                dict(
                    id=c.id,
                    espacio=c.espacio,
                    codigo=c.codigo,
                    corte=fila.corte,
                    version=fila.version,
                    fecha=fila.creado.isoformat() + "Z",
                    **fila.datos,
                ),
            )
        return dict(modelo=entrenar()[1], items=list(ultimos.values()))


@router.post("/predicciones/evaluar")
def actualizar(request: Request):
    evaluar(request.app.state.motor)
    return {"mensaje": "Revisión experimental registrada."}
