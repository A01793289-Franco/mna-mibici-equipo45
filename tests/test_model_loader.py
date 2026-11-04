
"""Pruebas unitarias del cargador MLflow para despliegue."""

from unittest import mock

import pytest

from mibici.model_loader import load_registered_model
from mibici.train import REGISTERED_MODELS


@mock.patch("mibici.model_loader.load_champion")
@mock.patch("mibici.model_loader.mlflow.set_tracking_uri")
def test_load_registered_model_success(
    mock_set_tracking_uri, mock_load_champion, monkeypatch
):
    """Verifica la carga de P1 desde un Registry configurado."""
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://localhost:5000")

    fake_model = mock.Mock()
    mock_load_champion.return_value = (
        fake_model,
        ["station_id", "hour"],
    )

    result = load_registered_model(question="P1")

    mock_set_tracking_uri.assert_called_once_with(
        "http://localhost:5000"
    )
    mock_load_champion.assert_called_once_with("P1", "champion")

    expected_uri = f"models:/{REGISTERED_MODELS['P1']}@champion"
    assert result["model"] is fake_model
    assert result["model_uri"] == expected_uri
    assert result["columns"] == ["station_id", "hour"]


def test_load_registered_model_without_tracking_uri(monkeypatch):
    """Verifica el error cuando falta la dirección de MLflow."""
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)

    with pytest.raises(ValueError, match="MLFLOW_TRACKING_URI"):
        load_registered_model(question="P1")


def test_load_registered_model_invalid_question(monkeypatch):
    """Verifica que se rechacen preguntas desconocidas."""
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://localhost:5000")

    with pytest.raises(ValueError, match="Pregunta no soportada"):
        load_registered_model(question="P4")
