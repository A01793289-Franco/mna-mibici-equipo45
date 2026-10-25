"""Pruebas de la inferencia con un modelo registrado en un MLflow temporal y datos sintéticos."""

import contextlib
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np
import pandas as pd

from mibici import config as cfg
from mibici import predict, train

STATIONS = 3


def feature_table(seed=0, hours=400):
    """Tabla sintética con una fila por estación y hora local, como la tabla real de variables."""
    rng = np.random.default_rng(seed)
    count = hours * STATIONS
    stamps = pd.date_range("2026-03-01", periods=hours, freq="h", tz=cfg.TIMEZONE)
    frame = pd.DataFrame(
        {
            "station_id": np.tile(np.arange(1, STATIONS + 1), hours).astype("int32"),
            "timestamp": stamps[np.arange(count) // STATIONS],
            "split": np.where(np.arange(count) < count * 0.6, "train", "val"),
        }
    )
    for column in cfg.P2_FEATURE_COLUMNS:
        frame[column] = rng.poisson(2, count).astype(float)
    frame["target_departures"] = rng.poisson(2, count).astype("int32")
    frame["target_risk"] = rng.integers(0, 3, count).astype("int8")
    return frame


class TestPredict(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(cls.temp.name)
        cls.mlflow = train.configure_mlflow(
            tracking_uri=f"sqlite:///{(root / 'mlflow.db').as_posix()}",
            experiment="prueba-predict",
            artifact_root=root / "artefactos",
        )
        context = {
            "git_commit": "abc",
            "git_dirty": "false",
            "data_version": "d",
            "feature_version": "f",
        }
        cls.data = feature_table()
        cls.p1 = cls.data[["station_id", "timestamp", *cfg.P1_FEATURE_COLUMNS]]
        cls.p2 = cls.data[["station_id", "timestamp", *cfg.P2_FEATURE_COLUMNS]]
        train.run_p1(cls.data, figures_dir=root / "figs", context=context)
        train.run_p2(cls.data, figures_dir=root / "figs", context=context)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_p1_returns_one_row_per_station_and_matches_loaded_model(self):
        when = self.p1["timestamp"].iloc[600]
        result = predict.predict_hour("P1", when, table=self.p1)
        rows = self.p1[self.p1["timestamp"] == when].sort_values("station_id")
        self.assertEqual(result["station_id"].tolist(), rows["station_id"].tolist())
        model = self.mlflow.sklearn.load_model("models:/mibici-p1-demanda@champion")
        np.testing.assert_allclose(
            result["demanda_esperada"], model.predict(rows[list(cfg.P1_FEATURE_COLUMNS)])
        )

    def test_p2_has_class_names_and_probabilities_that_add_one(self):
        when = self.p2["timestamp"].iloc[600]
        result = predict.predict_hour("P2", when, table=self.p2)
        probabilities = result[[f"prob_{name}" for name in cfg.P2_CLASS_NAMES]]
        np.testing.assert_allclose(probabilities.sum(axis=1), 1.0)
        self.assertTrue(set(result["riesgo"]) <= set(cfg.P2_CLASS_NAMES))

    def test_hour_without_features_gives_clear_error_with_range(self):
        with self.assertRaises(predict.PredictionError) as caught:
            predict.predict_hour("P1", "2020-01-01T08:00", table=self.p1)
        self.assertIn("La tabla cubre de", str(caught.exception))

    def test_naive_timestamp_is_read_in_project_timezone(self):
        when = self.p1["timestamp"].iloc[300]
        naive = when.tz_localize(None).isoformat()
        self.assertEqual(len(predict.predict_hour("P1", naive, table=self.p1)), STATIONS)

    def test_missing_champion_alias_explains_how_to_train(self):
        with self.assertRaises(predict.PredictionError) as caught:
            predict.load_champion("P1", alias="no-existe")
        self.assertIn("mibici.train", str(caught.exception))

    def test_unknown_question_is_rejected(self):
        with self.assertRaises(predict.PredictionError):
            predict.load_champion("P3")

    def patched_main(self):
        """``main`` apunta MLflow a la base real del repo; en pruebas se conserva la temporal."""
        stack = contextlib.ExitStack()
        stack.enter_context(mock.patch.object(predict, "configure_mlflow"))
        stack.enter_context(mock.patch.object(pd, "read_parquet", return_value=self.p1))
        return stack

    def test_main_writes_csv(self):
        when = self.p1["timestamp"].iloc[600]
        output = Path(self.temp.name) / "salida.csv"
        with self.patched_main():
            predict.main(
                ["--question", "P1", "--timestamp", when.isoformat(), "--output", str(output)]
            )
        self.assertEqual(len(pd.read_csv(output)), STATIONS)

    def test_main_exits_with_message_when_hour_is_missing(self):
        with self.patched_main():
            with self.assertRaises(SystemExit) as caught:
                predict.main(["--question", "P1", "--timestamp", "2020-01-01T08:00"])
        self.assertIn("No hay variables", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
