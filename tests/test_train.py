"""Pruebas del entrenamiento con tablas sintéticas: sin datos reales ni red."""

from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from mibici import config as cfg
from mibici import train


def demand_table(rows_per_split=300, seed=0):
    rng = np.random.default_rng(seed)
    frames = []
    for split, count in (("train", rows_per_split), ("val", rows_per_split // 2), ("test", 50)):
        frame = pd.DataFrame(
            {
                "station_id": rng.integers(1, 4, count).astype("int32"),
                "timestamp": pd.date_range("2026-01-01", periods=count, freq="h"),
                "split": split,
                "hour": rng.integers(0, 24, count).astype("int8"),
                "weekday": rng.integers(0, 7, count).astype("int8"),
                "is_weekend": rng.integers(0, 2, count).astype("int8"),
                "month": 3,
            }
        )
        for column in cfg.P1_FEATURE_COLUMNS:
            if column not in frame:
                frame[column] = rng.poisson(2, count).astype(float)
        frame["target_departures"] = rng.poisson(2, count).astype("int32")
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def risk_table(seed=0):
    data = demand_table(seed=seed)
    rng = np.random.default_rng(seed)
    for column in cfg.P2_FEATURE_COLUMNS:
        if column not in data:
            data[column] = rng.normal(0, 1, len(data))
    data["target_risk"] = rng.integers(0, 3, len(data)).astype("int8")
    return data


def profile_table(seed=0, stations=60):
    """Tres perfiles claros (pico en 7, 13 y 19 h) con ruido pequeño."""
    rng = np.random.default_rng(seed)
    centers = np.array([7, 13, 19])
    rows = []
    for station in range(stations):
        peak = centers[station % 3]
        base = np.exp(-0.5 * ((np.arange(24) - peak) / 1.5) ** 2) + rng.normal(0, 0.01, 24).clip(0)
        profile = np.concatenate([base, base])
        rows.append(profile / profile.sum())
    frame = pd.DataFrame(rows, columns=list(cfg.P3_FEATURE_COLUMNS))
    frame.insert(0, "station_id", np.arange(stations, dtype="int32"))
    frame["name"] = [f"E{i}" for i in range(stations)]
    frame["latitude"] = 20.6 + rng.normal(0, 0.02, stations)
    frame["longitude"] = -103.3 + rng.normal(0, 0.02, stations)
    return frame


class TestMetrics(unittest.TestCase):
    def test_wape_matches_definition_and_handles_zero_demand(self):
        self.assertAlmostEqual(train.wape([2, 0, 4], [1, 1, 4]), 2 / 6)
        self.assertTrue(np.isnan(train.wape([0, 0], [1, 2])))

    def test_regression_metrics_use_prefix(self):
        metrics = train.regression_metrics([1, 2, 3], [1, 2, 3], "val")
        self.assertEqual(metrics["val_mae"], 0.0)
        self.assertEqual(set(metrics), {"val_mae", "val_rmse", "val_wape", "val_r2"})

    def test_classification_metrics_do_not_invent_values_for_missing_classes(self):
        y_true = np.array([0, 0, 1, 1])
        proba = np.array([[0.9, 0.1, 0.0], [0.8, 0.2, 0.0], [0.1, 0.9, 0.0], [0.2, 0.8, 0.0]])
        metrics, undefined = train.classification_metrics(y_true, y_true, proba, "val")
        self.assertEqual(metrics["val_f1_macro"], 2 / 3)
        self.assertEqual(metrics["val_ap_normal"], 1.0)
        self.assertIn("val_ap_riesgo_sin_anclajes", undefined)
        self.assertNotIn("val_ap_riesgo_sin_anclajes", metrics)

    def test_probabilities_require_all_classes_in_training(self):
        data = risk_table()
        model = train.make_risk_model().fit(
            data[data.target_risk != 2][list(cfg.P2_FEATURE_COLUMNS)],
            data[data.target_risk != 2]["target_risk"],
        )
        with self.assertRaises(ValueError):
            train.class_probabilities(model, data[list(cfg.P2_FEATURE_COLUMNS)])


class TestBaselines(unittest.TestCase):
    def test_weekly_baseline_is_lag_168_when_available(self):
        data = demand_table()
        frame = data[data.split == "val"]
        np.testing.assert_array_equal(
            train.weekly_baseline(data[data.split == "train"], frame),
            frame["departures_lag_168"].to_numpy(),
        )

    def test_weekly_baseline_fallback_uses_only_training(self):
        base = {"weekday": 1, "hour": 8, "departures_lag_168": np.nan}
        training = pd.DataFrame(
            {"station_id": [1, 1], "weekday": [1, 1], "hour": [8, 8], "target_departures": [2, 4]}
        )
        frame = pd.DataFrame([{**base, "station_id": 1}, {**base, "station_id": 9}])
        prediction = train.weekly_baseline(training, frame)
        self.assertEqual(prediction[0], 3.0)  # promedio de la estación, día y hora
        self.assertEqual(prediction[1], 3.0)  # estación no vista: promedio global de entrenamiento


class TestClusters(unittest.TestCase):
    def test_separated_profiles_are_recovered_and_stable(self):
        for algorithm in train.CLUSTERERS:
            labels, metrics = train.cluster_metrics(
                profile_table(seed=1), profile_table(seed=2), algorithm
            )
            self.assertEqual(len(set(labels)), cfg.N_CLUSTERS)
            self.assertGreater(metrics["train_silhouette"], 0.5)
            self.assertGreater(metrics["val_ari"], 0.9)
            self.assertEqual(metrics["val_common_stations"], 60)


class TestChampion(unittest.TestCase):
    """La regla de elección usa solo métricas de validación."""

    def test_p1_picks_lowest_val_mae_and_ignores_test_metrics(self):
        candidates = {
            "base": ("r1", {"val_mae": 0.9, "test_mae": 0.1}, False),
            "modelo": ("r2", {"val_mae": 0.7, "test_mae": 5.0}, True),
        }
        self.assertEqual(train.pick_champion("P1", candidates), "modelo")

    def test_p2_picks_highest_val_f1_macro(self):
        candidates = {
            "a": ("r1", {"val_f1_macro": 0.82}, True),
            "b": ("r2", {"val_f1_macro": 0.87}, True),
        }
        self.assertEqual(train.pick_champion("P2", candidates), "b")

    def test_baseline_winning_means_nothing_to_register(self):
        candidates = {
            "base": ("r1", {"val_mae": 0.5}, False),
            "modelo": ("r2", {"val_mae": 0.7}, True),
        }
        self.assertIsNone(train.pick_champion("P1", candidates))

    def test_undefined_metric_disqualifies_run(self):
        candidates = {
            "a": ("r1", {"val_f1_macro": float("nan")}, True),
            "b": ("r2", {"val_f1_macro": 0.6}, True),
        }
        self.assertEqual(train.pick_champion("P2", candidates), "b")
        self.assertIsNone(train.pick_champion("P2", {"a": candidates["a"]}))


class TestMlflowRuns(unittest.TestCase):
    """Cada modelo debe quedar como un run con etiquetas, parámetros, métricas y artefactos."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(
            ignore_cleanup_errors=True
        )  # Windows mantiene abierto mlflow.db
        root = Path(cls.temp.name)
        cls.root = root
        cls.mlflow = train.configure_mlflow(
            tracking_uri=f"sqlite:///{(root / 'mlflow.db').as_posix()}",
            experiment="prueba-equipo45",
            artifact_root=root / "artefactos",
        )
        cls.context = {
            "git_commit": "abc123",
            "git_dirty": "false",
            "data_version": "datos-v1",
            "feature_version": "vars-v1",
        }

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def runs(self, question):
        client = self.mlflow.tracking.MlflowClient()
        experiment = client.get_experiment_by_name("prueba-equipo45")
        return client, client.search_runs(
            [experiment.experiment_id], filter_string=f"tags.pregunta = '{question}'"
        )

    def test_p1_logs_baseline_and_candidate(self):
        results = train.run_p1(
            demand_table(), figures_dir=self.root / "figs", context=self.context
        )
        self.assertEqual(set(results), {"P1_estacional_h1", "P1_hgb_poisson_h1"})
        client, runs = self.runs("P1")
        self.assertEqual(len(runs), 2)
        for run in runs:
            self.assertEqual(run.data.tags["equipo"], cfg.TEAM)
            self.assertEqual(run.data.tags["git_commit"], "abc123")
            self.assertEqual(run.data.params["data_version"], "datos-v1")
            self.assertEqual(run.data.params["seed"], str(cfg.SEED))
            self.assertIn("val_mae", run.data.metrics)
            self.assertFalse(any(name.startswith("test_") for name in run.data.metrics))
            self.assertTrue(client.list_artifacts(run.info.run_id, "figuras"))

    def test_p1_saves_model_with_signature_and_registers_champion(self):
        results = train.run_p1(
            demand_table(), figures_dir=self.root / "figs", context=self.context
        )
        client, runs = self.runs("P1")
        for run in runs:
            if run.info.run_name == "P1_estacional_h1":
                self.assertEqual(run.outputs.model_outputs, [])
        candidates = [run for run in runs if run.info.run_name == "P1_hgb_poisson_h1"]
        candidate = max(candidates, key=lambda run: run.info.start_time)
        self.assertEqual(len(candidate.outputs.model_outputs), 1)
        uri = f"runs:/{candidate.info.run_id}/{train.MODEL_ARTIFACT}"
        info = self.mlflow.models.get_model_info(uri)
        self.assertEqual(info.signature.inputs.input_names(), list(cfg.P1_FEATURE_COLUMNS))
        data = demand_table()
        val = data[data.split == "val"]
        expected = results["P1_hgb_poisson_h1"]["val_mae"]
        model = self.mlflow.sklearn.load_model(uri)
        predicted = model.predict(val[list(cfg.P1_FEATURE_COLUMNS)])
        self.assertAlmostEqual(np.abs(val["target_departures"] - predicted).mean(), expected)
        alias = client.get_model_version_by_alias(train.REGISTERED_MODELS["P1"], "champion")
        self.assertEqual(alias.run_id, candidate.info.run_id)

    def test_register_false_leaves_registry_untouched(self):
        client = self.mlflow.tracking.MlflowClient()
        before = len(client.search_model_versions(f"name = '{train.REGISTERED_MODELS['P1']}'"))
        train.run_p1(
            demand_table(), figures_dir=self.root / "figs", context=self.context, register=False
        )
        after = len(client.search_model_versions(f"name = '{train.REGISTERED_MODELS['P1']}'"))
        self.assertEqual(before, after)

    def test_p1_test_metrics_only_with_final_test(self):
        results = train.run_p1(
            demand_table(),
            final_test=True,
            figures_dir=self.root / "figs",
            context=self.context,
        )
        self.assertIn("test_mae", results["P1_hgb_poisson_h1"])

    def test_p2_logs_class_metrics_and_confusion_matrix(self):
        results = train.run_p2(risk_table(), figures_dir=self.root / "figs", context=self.context)
        self.assertEqual(set(results), {"P2_logistica_proxy_h1", "P2_hgb_proxy_h1"})
        client, runs = self.runs("P2")
        self.assertEqual(len(runs), 2)
        for run in runs:
            self.assertIn("val_f1_macro", run.data.metrics)
            self.assertIn("val_recall_riesgo_sin_bicicletas", run.data.metrics)
            self.assertTrue(client.list_artifacts(run.info.run_id, "figuras"))
            self.assertEqual(len(run.outputs.model_outputs), 1)
        champion = client.get_model_version_by_alias(train.REGISTERED_MODELS["P2"], "champion")
        latest = sorted(runs, key=lambda run: run.info.start_time)[-2:]
        winner = max(latest, key=lambda run: run.data.metrics["val_f1_macro"])
        self.assertEqual(champion.run_id, winner.info.run_id)

    def test_p3_logs_groups_map_and_table(self):
        tables = {"train": profile_table(seed=1), "val": profile_table(seed=2)}
        results = train.run_p3(
            tables,
            figures_dir=self.root / "figs",
            output_dir=self.root / "tablas",
            context=self.context,
        )
        self.assertEqual(set(results), {"P3_kmeans_perfil48", "P3_ward_perfil48"})
        client, runs = self.runs("P3")
        for run in runs:
            self.assertIn("val_ari", run.data.metrics)
            self.assertTrue(client.list_artifacts(run.info.run_id, "tablas"))
            self.assertEqual(
                run.data.params["coordenadas_en_agrupacion"], "no (solo para el mapa)"
            )


if __name__ == "__main__":
    unittest.main()
