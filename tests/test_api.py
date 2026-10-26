import unittest
from unittest import mock

from fastapi.testclient import TestClient
import pandas as pd

from mibici import api
from mibici.deployable import PersistenceRisk, SeasonalDemand
from mibici.predict import PredictionError


class TestAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api.app)
        self.when = pd.Timestamp("2026-08-15T08:00", tz=api.cfg.TIMEZONE)
        self.frame = pd.DataFrame(
            {
                "station_id": [1],
                "timestamp": [self.when],
                "hour": [8],
                "weekday": [5],
                "departures_lag_168": [3.0],
                "virtual_occupancy": [0.05],
            }
        )
        self.payload = {"question": "P1", "station_id": 1, "timestamp": "2026-08-15T08:00"}

    def request(self, model, columns, frame=None):
        with (
            mock.patch.object(api, "configure_mlflow"),
            mock.patch.object(api, "load_champion", return_value=(model, columns)),
            mock.patch.object(
                api.pd, "read_parquet", return_value=self.frame if frame is None else frame
            ) as read,
        ):
            response = self.client.post("/predict", json=self.payload)
        return response, read

    def test_health_and_openapi_do_not_require_models(self):
        with mock.patch.object(api, "load_champion") as load:
            self.assertEqual(self.client.get("/health").status_code, 200)
            spec = self.client.get("/openapi.json").json()
            self.assertIn("/predict", spec["paths"])
            self.assertEqual(self.client.get("/docs").status_code, 200)
            load.assert_not_called()

    def test_p1_matches_direct_prediction_and_filters_station_hour(self):
        columns = ["station_id", "weekday", "hour", "departures_lag_168"]
        model = SeasonalDemand().fit(self.frame[columns], [2])
        response, read = self.request(model, columns)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["prediction"]["station_id"], 1)
        self.assertEqual(
            result["prediction"]["demanda_esperada"], model.predict(self.frame[columns])[0]
        )
        self.assertEqual(result["model_uri"], "models:/mibici-p1-demanda@champion")
        self.assertEqual(
            read.call_args.kwargs["filters"],
            [("station_id", "=", 1), ("timestamp", "=", self.when)],
        )

    def test_p2_returns_risk_and_valid_probabilities(self):
        self.payload["question"] = "P2"
        columns = ["virtual_occupancy"]
        model = PersistenceRisk().fit(self.frame[columns])
        response, _ = self.request(model, columns)
        self.assertEqual(response.status_code, 200)
        record = response.json()["prediction"]
        self.assertEqual(record["clase"], 1)
        self.assertEqual(record["riesgo"], "riesgo_sin_bicicletas")
        self.assertAlmostEqual(sum(v for k, v in record.items() if k.startswith("prob_")), 1)

    def test_unknown_station_or_hour_returns_404(self):
        self.payload["station_id"] = 99999
        response, _ = self.request(mock.Mock(), ["hour"], frame=self.frame.iloc[:0])
        self.assertEqual(response.status_code, 404)
        self.assertIn("estación y hora", response.json()["detail"])

    def test_invalid_payloads_return_422_without_loading_a_model(self):
        for changes in (
            {"question": "P3"},
            {"station_id": -1},
            {"station_id": "1"},
            {"timestamp": "no-fecha"},
            {"timestamp": "2026-08-15T08:30"},
            {"extra": True},
        ):
            with self.subTest(changes=changes), mock.patch.object(api, "load_champion") as load:
                response = self.client.post("/predict", json={**self.payload, **changes})
                self.assertEqual(response.status_code, 422)
                load.assert_not_called()

    def test_missing_model_returns_503(self):
        with (
            mock.patch.object(api, "configure_mlflow"),
            mock.patch.object(api, "load_champion", side_effect=PredictionError("missing")),
        ):
            self.assertEqual(self.client.post("/predict", json=self.payload).status_code, 503)

    def test_missing_features_return_503(self):
        with (
            mock.patch.object(api, "configure_mlflow"),
            mock.patch.object(api, "load_champion", return_value=(mock.Mock(), ["hour"])),
            mock.patch.object(api.pd, "read_parquet", side_effect=FileNotFoundError()),
        ):
            self.assertEqual(self.client.post("/predict", json=self.payload).status_code, 503)

    def test_duplicate_station_hour_is_not_silently_accepted(self):
        response, _ = self.request(mock.Mock(), ["hour"], pd.concat([self.frame, self.frame]))
        self.assertEqual(response.status_code, 503)
        self.assertIn("duplicadas", response.json()["detail"])

    def test_timezone_aware_time_matches_the_same_local_hour(self):
        self.payload["timestamp"] = "2026-08-15T14:00:00Z"
        columns = ["station_id", "weekday", "hour", "departures_lag_168"]
        response, read = self.request(SeasonalDemand().fit(self.frame[columns], [2]), columns)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(read.call_args.kwargs["filters"][1][2], self.when)


if __name__ == "__main__":
    unittest.main()
