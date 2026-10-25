"""Predicción por estación con el modelo campeón del Model Registry de MLflow.

Uso desde la raíz del repositorio (después de ``python -m mibici.train``)::

    python -m mibici.predict --question P1 --timestamp 2026-09-15T08:00
    python -m mibici.predict --question P2 --timestamp 2026-09-15T08:00 --output salida.csv

Carga la versión con alias ``champion`` de ``mibici-p1-demanda`` (demanda esperada de salidas en
esa hora) o de ``mibici-p2-riesgo`` (clase de riesgo y probabilidades), toma las filas de esa hora
de la tabla de variables que construye ``mibici/features.py`` y escribe un CSV con una fila por
estación. No recalcula variables aquí: usar la misma tabla que en el entrenamiento evita el
desfase entre entrenamiento y servicio (training-serving skew). Las columnas se ordenan según la
firma guardada con el modelo.

La hora debe existir en la tabla de variables (con historia suficiente para los rezagos de 168 h).
Una fecha sin filas produce un error con el rango disponible, no un CSV vacío. La hora se interpreta
en la zona ``config.TIMEZONE`` si no incluye zona.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

from mibici import config as cfg
from mibici.features import local_time
from mibici.train import (
    CHAMPION_ALIAS,
    REGISTERED_MODELS,
    class_probabilities,
    configure_mlflow,
)

PREDICTIONS_DIR = cfg.ROOT_DIR / "reports" / "predicciones"
QUESTIONS = tuple(REGISTERED_MODELS)


class PredictionError(ValueError):
    """Entrada que no permite predecir: pregunta, modelo, fecha o columnas inválidas."""


def load_champion(question, alias=CHAMPION_ALIAS):
    """Carga el modelo registrado y regresa ``(modelo, columnas en el orden de la firma)``."""
    import mlflow
    from mlflow.exceptions import MlflowException

    if question not in REGISTERED_MODELS:
        raise PredictionError(f"Pregunta no soportada: {question}. Usa {', '.join(QUESTIONS)}.")
    uri = f"models:/{REGISTERED_MODELS[question]}@{alias}"
    try:
        info = mlflow.models.get_model_info(uri)
        model = mlflow.sklearn.load_model(uri)
    except MlflowException as error:
        raise PredictionError(
            f"No hay modelo {uri}. Entrena y registra primero con: "
            f"python -m mibici.train --question {question}"
        ) from error
    return model, list(info.signature.inputs.input_names())


def features_table(question):
    """Ruta de la tabla de variables de la pregunta."""
    return cfg.FEATURE_FILES["p1" if question == "P1" else "p2"]


def select_hour(table, timestamp):
    """Filas de una hora exacta; falla con el rango disponible si no hay ninguna."""
    when = local_time(timestamp)
    rows = table[table["timestamp"] == when]
    if rows.empty:
        first, last = table["timestamp"].min(), table["timestamp"].max()
        raise PredictionError(
            f"No hay variables para {when.isoformat()}. La tabla cubre de {first.isoformat()} a "
            f"{last.isoformat()} (las primeras horas se excluyen por falta de 168 h de historia)."
        )
    return rows


def predict_hour(question, timestamp, table=None, model=None, columns=None, alias=CHAMPION_ALIAS):
    """Predice una hora para todas las estaciones con fila en la tabla de variables."""
    if model is None:
        model, columns = load_champion(question, alias)
    if table is None:
        table = pd.read_parquet(
            features_table(question), columns=["station_id", "timestamp", *columns]
        )
    missing = [name for name in columns if name not in table.columns]
    if missing:
        raise PredictionError(f"Faltan columnas que pide el modelo: {', '.join(missing)}")
    rows = select_hour(table, timestamp).sort_values("station_id")
    features = rows[columns]
    result = rows[["station_id", "timestamp"]].reset_index(drop=True)
    if question == "P1":
        result["demanda_esperada"] = model.predict(features)
    else:
        probabilities = class_probabilities(model, features)
        result["clase"] = probabilities.argmax(axis=1)
        result["riesgo"] = [cfg.P2_CLASS_NAMES[label] for label in result["clase"]]
        for label, name in enumerate(cfg.P2_CLASS_NAMES):
            result[f"prob_{name}"] = probabilities[:, label]
    return result


def default_output(question, timestamp):
    """Nombre de salida por defecto: ``reports/predicciones/p1_20260915T0800.csv``."""
    stamp = local_time(timestamp).strftime("%Y%m%dT%H%M")
    return PREDICTIONS_DIR / f"{question.lower()}_{stamp}.csv"


def main(argv=None):
    """Predice una hora y escribe el CSV."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--question", choices=QUESTIONS, required=True)
    parser.add_argument("--timestamp", required=True, help="hora local, p. ej. 2026-09-15T08:00")
    parser.add_argument("--output", type=Path, help="CSV de salida (por defecto en reports/)")
    parser.add_argument("--alias", default=CHAMPION_ALIAS, help="alias del modelo registrado")
    args = parser.parse_args(argv)
    configure_mlflow()
    try:
        result = predict_hour(args.question, args.timestamp, alias=args.alias)
    except (PredictionError, ValueError) as error:
        sys.exit(f"Error: {error}")
    output = args.output or default_output(args.question, args.timestamp)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False)
    print(f"{len(result)} estaciones -> {output}", flush=True)


if __name__ == "__main__":
    main()
