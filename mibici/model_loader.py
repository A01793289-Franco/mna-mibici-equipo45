
"""Integración del Model Registry de MLflow para despliegue externo."""

import os

import mlflow

from mibici.predict import load_champion
from mibici.train import REGISTERED_MODELS


def load_registered_model(question="P1", alias="champion"):
    """Carga un modelo registrado usando un servidor MLflow externo."""

    if question not in REGISTERED_MODELS:
        raise ValueError(f"Pregunta no soportada: {question}")

    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")

    if not tracking_uri:
        raise ValueError(
            "Configura MLFLOW_TRACKING_URI para conectar con MLflow."
        )

    mlflow.set_tracking_uri(tracking_uri)

    model, columns = load_champion(question, alias)

    return {
        "model": model,
        "model_uri": f"models:/{REGISTERED_MODELS[question]}@{alias}",
        "columns": columns,
    }
