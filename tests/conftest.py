"""Fixtures compartidas por las pruebas PyTest: tablas sintéticas y MLflow temporal.

Reutiliza los generadores de ``test_train.py`` para que todas las pruebas usen las mismas
tablas sintéticas, sin datos reales ni red.
"""

import pytest

from mibici import train
from tests.test_train import demand_table, profile_table, risk_table

CONTEXT = {
    "git_commit": "abc123",
    "git_dirty": "false",
    "data_version": "datos-v1",
    "feature_version": "vars-v1",
}


@pytest.fixture
def demand_data():
    """Tabla P1 con particiones train, val y test."""
    return demand_table()


@pytest.fixture
def risk_data():
    """Tabla P2 con las tres clases de riesgo."""
    return risk_table()


@pytest.fixture
def profile_tables():
    """Perfiles P3 de entrenamiento y validación con tres grupos claros."""
    return {"train": profile_table(seed=1), "val": profile_table(seed=2)}


@pytest.fixture
def mlflow_store(tmp_path):
    """MLflow con SQLite y artefactos en una carpeta temporal; no toca ``mlflow.db``."""
    mlflow = train.configure_mlflow(
        tracking_uri=f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}",
        experiment="prueba-pytest",
        artifact_root=tmp_path / "artefactos",
    )
    yield mlflow
    mlflow.end_run()


@pytest.fixture
def run_context():
    """Contexto fijo de Git y versiones para los runs de prueba."""
    return dict(CONTEXT)
