
"""Recuperación de modelos registrados en MLflow para despliegue."""

import os

import mlflow
import mlflow.sklearn

from mibici.train import REGISTERED_MODELS


def load_registered_model(question="P1", alias="champion"):
    """Recupera un modelo y su firma desde MLflow Model Registry."""

    if question not in REGISTERED_MODELS:
        raise ValueError(f"Pregunta no soportada: {question}")

    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")

    if not tracking_uri:
        raise ValueError(
            "Configura MLFLOW_TRACKING_URI para conectar con MLflow."
        )

    mlflow.set_tracking_uri(tracking_uri)

    model_name = REGISTERED_MODELS[question]
    model_uri = f"models:/{model_name}@{alias}"

    info = mlflow.models.get_model_info(model_uri)
    model = mlflow.sklearn.load_model(model_uri)

    columns = list(info.signature.inputs.input_names())

    return {
        "model": model,
        "model_uri": model_uri,
        "columns": columns,
    }
