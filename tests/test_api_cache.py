"""Pruebas del caché en memoria del champion en la API."""

import threading
import time
from unittest import mock

from fastapi import HTTPException
from fastapi.testclient import TestClient
from mlflow.exceptions import MlflowException
import pytest

from mibici import api
from mibici.predict import PredictionError
from tests.test_api_variables import P1_COLUMNS, P1_PAYLOAD


@pytest.fixture
def clock(monkeypatch):
    """Reloj controlado para vencer el caché sin esperar."""
    now = [1000.0]
    monkeypatch.setattr(api.time, "monotonic", lambda: now[0])
    return now


@pytest.fixture
def loader(monkeypatch):
    calls = []

    def load(question):
        calls.append(question)
        return object(), ["hour"]

    monkeypatch.setattr(api, "configure_mlflow", lambda: None)
    monkeypatch.setattr(api, "load_champion", load)
    return calls


def test_champion_is_loaded_once_while_cache_is_fresh(loader, clock):
    first = api.cached_champion("P1")
    clock[0] += api.MODEL_CACHE_SECONDS - 1
    second = api.cached_champion("P1")
    assert first == second
    assert loader == ["P1"]


def test_each_question_has_its_own_entry(loader, clock):
    api.cached_champion("P1")
    api.cached_champion("P2")
    api.cached_champion("P1")
    assert loader == ["P1", "P2"]


def test_champion_is_reloaded_after_cache_expires(loader, clock):
    first, _ = api.cached_champion("P1")
    clock[0] += api.MODEL_CACHE_SECONDS + 1
    second, _ = api.cached_champion("P1")
    assert loader == ["P1", "P1"]
    assert first is not second


def test_zero_seconds_disables_the_cache(loader, clock, monkeypatch):
    monkeypatch.setattr(api, "MODEL_CACHE_SECONDS", 0.0)
    api.cached_champion("P1")
    api.cached_champion("P1")
    assert loader == ["P1", "P1"]


@pytest.mark.parametrize(
    "error", [PredictionError("falta"), MlflowException("caído"), HTTPException(503)]
)
def test_failed_reload_keeps_serving_previous_model_and_delays_retry(
    loader, clock, monkeypatch, error
):
    old, columns = api.cached_champion("P1")
    clock[0] += api.MODEL_CACHE_SECONDS + 1
    monkeypatch.setattr(api, "load_champion", mock.Mock(side_effect=error))
    assert api.cached_champion("P1") == (old, columns)
    # Durante el tiempo de espera no se vuelve a consultar MLflow.
    clock[0] += api.MODEL_RETRY_SECONDS - 1
    assert api.cached_champion("P1") == (old, columns)
    assert api.load_champion.call_count == 1
    clock[0] += 2
    api.cached_champion("P1")
    assert api.load_champion.call_count == 2


def test_failure_without_previous_model_is_raised_and_not_cached(clock, monkeypatch):
    load = mock.Mock(side_effect=PredictionError("falta"))
    monkeypatch.setattr(api, "configure_mlflow", lambda: None)
    monkeypatch.setattr(api, "load_champion", load)
    for _ in range(2):
        with pytest.raises(PredictionError):
            api.cached_champion("P1")
    assert load.call_count == 2


def test_concurrent_first_requests_load_the_model_once(monkeypatch):
    calls = []

    def slow_load(question):
        calls.append(question)
        time.sleep(0.05)
        return object(), ["hour"]

    monkeypatch.setattr(api, "configure_mlflow", lambda: None)
    monkeypatch.setattr(api, "load_champion", slow_load)
    results = []
    threads = [
        threading.Thread(target=lambda: results.append(api.cached_champion("P1")))
        for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert calls == ["P1"]
    assert len({id(model) for model, _ in results}) == 1


def test_endpoint_does_not_reload_model_on_every_request(monkeypatch):
    import pandas as pd
    from sklearn.dummy import DummyRegressor

    frame = pd.DataFrame([P1_PAYLOAD])[P1_COLUMNS]
    model = DummyRegressor(strategy="constant", constant=3.25).fit(frame, [3.25])
    load = mock.Mock(return_value=(model, P1_COLUMNS))
    monkeypatch.setattr(api, "configure_mlflow", lambda: None)
    monkeypatch.setattr(api, "load_champion", load)
    client = TestClient(api.app)
    for _ in range(5):
        response = client.post("/predict/p1", json=P1_PAYLOAD)
        assert response.status_code == 200
        assert response.json()["prediction"] == {"demanda_esperada": 3.25}
    assert load.call_count == 1


def test_endpoint_returns_503_when_there_is_no_model_yet(monkeypatch):
    monkeypatch.setattr(api, "configure_mlflow", lambda: None)
    monkeypatch.setattr(api, "load_champion", mock.Mock(side_effect=PredictionError("falta")))
    response = TestClient(api.app).post("/predict/p1", json=P1_PAYLOAD)
    assert response.status_code == 503
