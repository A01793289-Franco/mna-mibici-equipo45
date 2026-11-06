import json

from fastapi.testclient import TestClient
import numpy as np
import pytest

from mibici import api, verify_api
from mibici.predict import PredictionError


class Demand:
    def __init__(self, value=2.5):
        self.value = value

    def predict(self, frame):
        return np.array([self.value])


class Risk:
    classes_ = np.array([0, 1, 2])

    def __init__(self, values=(0.2, 0.6, 0.2)):
        self.values = values

    def predict_proba(self, frame):
        return np.array([self.values])


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "configure_mlflow", lambda: None)
    monkeypatch.setattr(
        api, "load_champion", lambda question: (
            Demand() if question == "P1" else Risk(), ["hour"]
        )
    )
    return TestClient(api.app)


def test_http_verifier_checks_real_routes_and_invalid_inputs(client):
    result = verify_api.verify_api("http://testserver/", request=client.request)
    assert result["passed"] is True
    assert len(result["checks"]) == 11
    assert [c["status"] for c in result["checks"]] == [200] * 4 + [422] * 7


def test_unavailable_mode_distinguishes_health_from_model_readiness(client, monkeypatch):
    def unavailable(question):
        raise PredictionError("no champion")

    monkeypatch.setattr(api, "load_champion", unavailable)
    result = verify_api.verify_api("http://testserver", unavailable=True, request=client.request)
    assert result["mode"] == "unavailable"
    assert [c["status"] for c in result["checks"][:4]] == [200, 200, 503, 503]
    with pytest.raises(verify_api.VerificationError, match="HTTP 200; recibido 503"):
        verify_api.verify_api("http://testserver", request=client.request)


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf")])
def test_p1_never_publishes_invalid_model_predictions(client, monkeypatch, value):
    monkeypatch.setattr(api, "load_champion", lambda question: (Demand(value), ["hour"]))
    response = client.post("/predict/p1", json=verify_api.P1_EXAMPLE)
    assert response.status_code == 503
    assert response.json() == {"detail": "El modelo produjo una salida inválida"}


@pytest.mark.parametrize(
    "values", [(0.1, 0.1, 0.1), (-0.1, 0.5, 0.6), (float("nan"), 0.5, 0.5)]
)
def test_p2_never_publishes_invalid_model_probabilities(client, monkeypatch, values):
    monkeypatch.setattr(api, "load_champion", lambda question: (Risk(values), ["hour"]))
    response = client.post("/predict/p2", json=verify_api.P2_EXAMPLE)
    assert response.status_code == 503
    assert response.json() == {"detail": "El modelo produjo una salida inválida"}


def test_cli_preserves_failure_as_json_and_nonzero_exit(tmp_path, monkeypatch):
    def fail(*args):
        raise verify_api.VerificationError("falló el control HTTP")

    monkeypatch.setattr(verify_api, "verify_api", fail)
    output = tmp_path / "resultado.json"
    assert verify_api.main(["--output", str(output)]) == 1
    assert json.loads(output.read_text(encoding="utf-8")) == {
        "passed": False, "error": "falló el control HTTP"
    }
