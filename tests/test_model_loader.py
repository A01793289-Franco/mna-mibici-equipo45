
"""Pruebas unitarias de recuperación de modelos desde MLflow."""

from unittest import mock

import pytest

from mibici.model_loader import load_registered_model


@mock.patch("mibici.model_loader.mlflow")
def test_load_registered_model_success(mock_mlflow, monkeypatch):
    """Verifica la carga del modelo P1 desde un Registry externo."""
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://localhost:5000")

    fake_model = mock.Mock()
    mock_mlflow.sklearn.load_model.return_value = fake_model

    mock_info = mock.Mock()
    mock_info.signature.inputs.input_names.return_value = [
        "station_id",
        "hour",
    ]
    mock_mlflow.models.get_model_info.return_value = mock_info

    result = load_registered_model(question="P1")

    mock_mlflow.set_tracking_uri.assert_called_once_with(
        "http://localhost:5000"
    )
    mock_mlflow.sklearn.load_model.assert_called_once_with(
        "models:/mibici-p1-demanda@champion"
    )

    assert result["model"] is fake_model
    assert result["model_uri"] == "models:/mibici-p1-demanda@champion"
    assert result["columns"] == ["station_id", "hour"]


def test_load_registered_model_without_tracking_uri(monkeypatch):
    """Verifica el error cuando falta la dirección de MLflow."""
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)

    with pytest.raises(ValueError, match="MLFLOW_TRACKING_URI"):
        load_registered_model(question="P1")


def test_load_registered_model_invalid_question(monkeypatch):
    """Verifica que no se acepten modelos desconocidos."""
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://localhost:5000")

    with pytest.raises(ValueError, match="Pregunta no soportada"):
        load_registered_model(question="P4")
