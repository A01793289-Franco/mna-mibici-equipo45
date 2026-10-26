import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np
import pandas as pd

from mibici import train
from mibici.deployable import PersistenceRisk, SeasonalDemand, StationGroups
from mibici.tracking import check_registered_model, project_run


class TestDeployable(unittest.TestCase):
    def test_seasonal_roundtrip_semantics(self):
        frame = pd.DataFrame(
            {
                "station_id": [1, 1, 9],
                "weekday": [1, 1, 1],
                "hour": [8, 8, 8],
                "departures_lag_168": [2.0, np.nan, np.nan],
            }
        )
        model = SeasonalDemand().fit(frame.iloc[:2], [2, 4])
        np.testing.assert_array_equal(model.predict(frame), [2, 3, 3])

    def test_persistence_can_win_and_predict_probabilities(self):
        frame = pd.DataFrame({"virtual_occupancy": [0.05, 0.5, 0.95]})
        model = PersistenceRisk().fit(frame)
        np.testing.assert_array_equal(model.predict(frame), [1, 0, 2])
        np.testing.assert_array_equal(model.predict_proba(frame).sum(axis=1), [1, 1, 1])
        candidates = {
            "rule": ("a", {"val_f1_macro": 0.89}, True),
            "hgb": ("b", {"val_f1_macro": 0.87}, True),
        }
        self.assertEqual(train.pick_champion("P2", candidates), "rule")

    def test_ward_transfer_uses_frozen_training_profiles(self):
        frame = pd.DataFrame(
            [[0.0, 0.0], [0.1, 0.1], [10.0, 10.0], [10.1, 10.1]], columns=["a", "b"]
        )
        model = StationGroups("ward", n_clusters=2).fit(frame)
        before = model.labels_.copy()
        np.testing.assert_array_equal(model.predict(frame), before)
        self.assertEqual(model.assignment_rule_, "nearest_training_profile")
        model.predict(pd.DataFrame([[1000.0, -500.0]], columns=frame.columns))
        np.testing.assert_array_equal(model.labels_, before)


class TestRegistryIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.root = Path(cls.temp.name)
        cls.mlflow = train.configure_mlflow(
            tracking_uri=f"sqlite:///{(cls.root / 'mlflow.db').as_posix()}",
            experiment="integration-registry",
            artifact_root=cls.root / "artifacts",
        )
        cls.context = {
            "git_commit": "unit-test",
            "git_dirty": "false",
            "data_version": "unit-data",
            "feature_version": "unit-features",
        }

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_all_model_types_survive_registry_roundtrip(self):
        frames = {
            "P1": pd.DataFrame(
                {
                    "station_id": [1, 1, 2],
                    "weekday": [1, 1, 1],
                    "hour": [8, 8, 8],
                    "departures_lag_168": [2.0, 3.0, 4.0],
                }
            ),
            "P2": pd.DataFrame({"virtual_occupancy": [0.05, 0.5, 0.95]}),
            "P3": pd.DataFrame({"a": [0.0, 0.1, 10.0, 10.1], "b": [0.0, 0.1, 10.0, 10.1]}),
        }
        models = {
            "P1": SeasonalDemand().fit(frames["P1"], [2, 3, 4]),
            "P2": PersistenceRisk().fit(frames["P2"]),
            "P3": StationGroups("ward", n_clusters=2).fit(frames["P3"]),
        }
        for question, model in models.items():
            metric = train.CHAMPION_RULE[question][0]
            run_id = train.log_run(
                "roundtrip",
                question,
                "baseline",
                {
                    "modelo": type(model).__name__,
                    "data_version": "unit-data",
                    "feature_version": "unit-features",
                },
                {metric: 0.8},
                [],
                self.context,
                model=model,
                input_example=frames[question],
                training=frames[question],
            )
            train.register_champion(question, {"roundtrip": (run_id, {metric: 0.8}, True)})
            record = check_registered_model(train.REGISTERED_MODELS[question])
            self.assertEqual(record["status"], "passed")
            self.assertEqual(record["git_commit"], "unit-test")
            client = self.mlflow.tracking.MlflowClient()
            version = client.get_model_version_by_alias(
                train.REGISTERED_MODELS[question], "champion"
            )
            self.assertTrue(version.description)
            self.assertEqual(version.tags["validation_status"], "passed")
            self.assertTrue(client.list_artifacts(run_id, "data"))
            self.assertTrue(client.list_artifacts(run_id, "config"))
            self.assertTrue(client.get_run(run_id).inputs.dataset_inputs)

    def test_project_parent_is_preserved_and_each_candidate_is_child(self):
        parent = self.mlflow.start_run(run_name="project")
        run_id = parent.info.run_id
        self.mlflow.end_run()
        with mock.patch.dict(os.environ, {"MLFLOW_RUN_ID": run_id}):
            with project_run():
                child = train.log_run(
                    "child",
                    "P1",
                    "candidato",
                    {"modelo": "test"},
                    {"val_mae": 1.0},
                    [],
                    self.context,
                )
                self.assertEqual(self.mlflow.active_run().info.run_id, run_id)
        client = self.mlflow.tracking.MlflowClient()
        self.assertEqual(client.get_run(child).data.tags["mlflow.parentRunId"], run_id)

    def test_failed_load_does_not_replace_champion(self):
        frame = pd.DataFrame({"virtual_occupancy": [0.05, 0.5, 0.95]})
        model = PersistenceRisk().fit(frame)
        params = {
            "modelo": "PersistenceRisk",
            "data_version": "unit-data",
            "feature_version": "unit-features",
        }
        run_id = train.log_run(
            "promotion",
            "P2",
            "baseline",
            params,
            {"val_f1_macro": 0.8},
            [],
            self.context,
            model=model,
            input_example=frame,
        )
        candidates = {"promotion": (run_id, {"val_f1_macro": 0.8}, True)}
        train.register_champion("P2", candidates)
        client = self.mlflow.tracking.MlflowClient()
        name = train.REGISTERED_MODELS["P2"]
        before = client.get_model_version_by_alias(name, "champion").version
        with mock.patch.object(
            train, "check_registered_model", side_effect=ValueError("failed check")
        ):
            with self.assertRaises(ValueError):
                train.register_champion("P2", candidates)
        self.assertEqual(client.get_model_version_by_alias(name, "champion").version, before)

    def test_http_tracking_uses_server_artifact_location(self):
        with mock.patch.dict(os.environ, {"MLFLOW_TRACKING_URI": "http://127.0.0.1:5001"}):
            with (
                mock.patch.object(self.mlflow, "set_tracking_uri") as set_uri,
                mock.patch.object(self.mlflow, "get_experiment_by_name", return_value=None),
                mock.patch.object(self.mlflow, "create_experiment") as create,
                mock.patch.object(self.mlflow, "set_experiment"),
            ):
                train.configure_mlflow(experiment="http-test")
        set_uri.assert_called_once_with("http://127.0.0.1:5001")
        create.assert_called_once_with("http-test")


if __name__ == "__main__":
    unittest.main()
