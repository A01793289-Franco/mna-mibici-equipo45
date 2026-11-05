"""Pruebas de los endpoints /predict/p1 y /predict/p2, que reciben las variables del modelo."""

from unittest import mock

from fastapi.testclient import TestClient
import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import LogisticRegression

from mibici import api
from mibici import config as cfg
from mibici.predict import PredictionError

P1_PAYLOAD = {
    "station_id": 2,
    "hour": 8,
    "weekday": 5,
    "is_weekend": 1,
    "month": 8,
    "departures_lag_1": 2.0,
    "departures_lag_24": 3.0,
    "departures_lag_168": 4.0,
    "departures_mean_24": 2.5,
    "departures_mean_168": 3.5,
}
P2_PAYLOAD = {
    **P1_PAYLOAD,
    "virtual_occupancy": 0.05,
    "net_flow_lag_1": -1.0,
    "net_flow_lag_24": 0.5,
}
P1_COLUMNS = list(cfg.P1_FEATURE_COLUMNS)
P2_COLUMNS = list(cfg.P2_FEATURE_COLUMNS)


@pytest.fixture
def client():
    return TestClient(api.app)


@pytest.fixture
def p1_model():
    frame = pd.DataFrame([P1_PAYLOAD])[P1_COLUMNS]
    return DummyRegressor(strategy="constant", constant=3.25).fit(frame, [3.25])


@pytest.fixture
def p2_model():
    rng = np.random.default_rng(0)
    frame = pd.DataFrame(rng.random((30, len(P2_COLUMNS))), columns=P2_COLUMNS)
    return LogisticRegression(max_iter=200).fit(frame, np.tile([0, 1, 2], 10))


def post(client, path, payload, model=None, columns=None):
    with (
        mock.patch.object(api, "configure_mlflow"),
        mock.patch.object(api, "load_champion", return_value=(model, columns)) as load,
    ):
        return client.post(path, json=payload), load


def test_p1_returns_prediction_with_declared_schema(client, p1_model):
    response, load = post(client, "/predict/p1", P1_PAYLOAD, p1_model, P1_COLUMNS)
    assert response.status_code == 200
    assert response.json() == {
        "question": "P1",
        "model_uri": "models:/mibici-p1-demanda@champion",
        "prediction": {"demanda_esperada": 3.25},
    }
    load.assert_called_once_with("P1")


def test_p2_returns_class_and_probabilities_that_sum_to_one(client, p2_model):
    response, _ = post(client, "/predict/p2", P2_PAYLOAD, p2_model, P2_COLUMNS)
    assert response.status_code == 200
    body = response.json()
    prediction = body["prediction"]
    assert body["model_uri"] == "models:/mibici-p2-riesgo@champion"
    assert prediction["riesgo"] == cfg.P2_CLASS_NAMES[prediction["clase"]]
    probabilities = [v for k, v in prediction.items() if k.startswith("prob_")]
    assert len(probabilities) == 3
    assert sum(probabilities) == pytest.approx(1.0)
    assert prediction["clase"] == int(np.argmax(probabilities))


def test_model_receives_columns_in_signature_order(client):
    seen = {}

    class Recorder:
        def predict(self, frame):
            seen["columns"] = list(frame.columns)
            return np.array([1.0])

    columns = list(reversed(P1_COLUMNS))
    response, _ = post(client, "/predict/p1", P1_PAYLOAD, Recorder(), columns)
    assert response.status_code == 200
    assert seen["columns"] == columns


@pytest.mark.parametrize(
    "changes",
    [
        {"hour": 24},
        {"hour": -1},
        {"hour": "8"},
        {"hour": 8.5},
        {"weekday": 7},
        {"month": 0},
        {"is_weekend": 0},
        {"departures_lag_1": -1},
        {"departures_lag_24": "abc"},
        {"extra": 1},
        {"station_id": 0},
    ],
)
def test_invalid_p1_payload_returns_422_without_loading_a_model(client, changes):
    response, load = post(client, "/predict/p1", {**P1_PAYLOAD, **changes})
    assert response.status_code == 422
    load.assert_not_called()


def test_nan_is_rejected(client):
    body = '{"hour": 8, "weekday": 5, "is_weekend": 1, "month": 8, "departures_lag_1": NaN}'
    with mock.patch.object(api, "load_champion") as load:
        response = client.post(
            "/predict/p1", content=body, headers={"Content-Type": "application/json"}
        )
    assert response.status_code == 422
    load.assert_not_called()


@pytest.mark.parametrize("drop", ["station_id", "hour", "departures_lag_168", "month"])
def test_missing_field_returns_422(client, drop):
    payload = {k: v for k, v in P1_PAYLOAD.items() if k != drop}
    response, load = post(client, "/predict/p1", payload)
    assert response.status_code == 422
    load.assert_not_called()


@pytest.mark.parametrize(
    "changes",
    [{"virtual_occupancy": 1.5}, {"virtual_occupancy": -0.1}, {"net_flow_lag_1": "x"}],
)
def test_invalid_p2_payload_returns_422(client, changes):
    response, load = post(client, "/predict/p2", {**P2_PAYLOAD, **changes})
    assert response.status_code == 422
    load.assert_not_called()


def test_p2_requires_its_extra_variables(client):
    response, _ = post(client, "/predict/p2", P1_PAYLOAD)
    assert response.status_code == 422


def test_boundary_values_are_accepted(client, p1_model):
    payload = {**P1_PAYLOAD, "hour": 0, "weekday": 0, "is_weekend": 0, "month": 1}
    payload.update(departures_lag_1=0, departures_lag_24=0, departures_lag_168=0)
    response, _ = post(client, "/predict/p1", payload, p1_model, P1_COLUMNS)
    assert response.status_code == 200


def test_p2_champion_that_needs_station_id_gets_422_when_it_is_missing(client, p2_model):
    payload = {k: v for k, v in P2_PAYLOAD.items() if k != "station_id"}
    response, _ = post(client, "/predict/p2", payload, p2_model, ["station_id", *P2_COLUMNS])
    assert response.status_code == 422
    assert "station_id" in response.json()["detail"]


def test_station_id_is_used_when_the_champion_needs_it(client):
    class Recorder:
        def predict(self, frame):
            assert frame.loc[0, "station_id"] == 7
            return np.array([2.0])

    payload = {**P1_PAYLOAD, "station_id": 7}
    response, _ = post(client, "/predict/p1", payload, Recorder(), ["station_id", *P1_COLUMNS])
    assert response.status_code == 200


@pytest.mark.parametrize(
    "path,payload", [("/predict/p1", P1_PAYLOAD), ("/predict/p2", P2_PAYLOAD)]
)
def test_missing_champion_returns_503(client, path, payload):
    with (
        mock.patch.object(api, "configure_mlflow"),
        mock.patch.object(api, "load_champion", side_effect=PredictionError("missing")),
    ):
        assert client.post(path, json=payload).status_code == 503


def test_openapi_declares_request_and_response_schemas(client):
    spec = client.get("/openapi.json").json()
    for path, request_name, response_name in (
        ("/predict/p1", "P1Variables", "P1Response"),
        ("/predict/p2", "P2Variables", "P2Response"),
    ):
        operation = spec["paths"][path]["post"]
        body = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        ok = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        assert body.endswith(request_name)
        assert ok.endswith(response_name)
