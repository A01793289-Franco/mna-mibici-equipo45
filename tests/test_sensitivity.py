from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from mibici import config as cfg
from mibici import sensitivity, train
from tests.test_train import risk_table


class TestHelpers(unittest.TestCase):
    def test_suffix_rounds_to_percentage(self):
        self.assertEqual(sensitivity.suffix(0.25), "_occ25")
        self.assertEqual(sensitivity.suffix(0.5), "_occ50")
        self.assertEqual(sensitivity.suffix(0.75), "_occ75")
        self.assertEqual(sensitivity.suffix(0.05), "_occ05")

    def test_class_shares_sum_to_one_per_split(self):
        shares = sensitivity.class_shares(risk_table())
        for split in ("train", "val"):
            total = sum(shares[f"{split}_{name}"] for name in cfg.P2_CLASS_NAMES)
            self.assertAlmostEqual(total, 1.0)

    def test_check_matches_saved_detects_differences(self):
        table = risk_table().head(20)
        with tempfile.TemporaryDirectory() as folder:
            path = cfg.data_path(cfg.FEATURE_FILES["p2"], folder)
            path.parent.mkdir(parents=True, exist_ok=True)
            table.to_parquet(path, index=False)
            sensitivity.check_matches_saved(table, folder)
            changed = table.copy()
            changed.loc[0, "target_risk"] = (changed.loc[0, "target_risk"] + 1) % 3
            with self.assertRaises(AssertionError):
                sensitivity.check_matches_saved(changed, folder)


class TestScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.root = Path(cls.temp.name)
        cls.mlflow = train.configure_mlflow(
            tracking_uri=f"sqlite:///{(cls.root / 'mlflow.db').as_posix()}",
            experiment="prueba-sensibilidad",
            artifact_root=cls.root / "artefactos",
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

    def test_each_scenario_is_a_run_and_nothing_is_registered(self):
        values = (0.25, 0.75)
        tables = {initial: risk_table(seed=int(initial * 100)) for initial in values}
        diagnostics = {initial: {"clipped_events": 10 + i} for i, initial in enumerate(values)}
        figures = self.root / "figs"
        summary = sensitivity.run_scenarios(tables, diagnostics, self.context, figures)
        self.assertEqual(len(summary), len(values) * len(sensitivity.MODELS))
        self.assertEqual(set(summary["ocupacion_inicial"]), set(values))
        self.assertTrue((figures / "p2_sensibilidad_ocupacion_inicial.png").is_file())
        self.assertTrue((figures / "p2_sensibilidad_ocupacion_inicial.csv").is_file())
        client = self.mlflow.tracking.MlflowClient()
        experiment = client.get_experiment_by_name("prueba-sensibilidad")
        runs = client.search_runs([experiment.experiment_id])
        names = {run.info.run_name for run in runs}
        self.assertIn(sensitivity.RUN_NAME, names)
        self.assertIn("P2_hgb_proxy_h1_occ25", names)
        self.assertIn("P2_persistencia_proxy_h1_occ75", names)
        by_name = {run.info.run_name: run for run in runs}
        self.assertEqual(by_name["P2_hgb_proxy_h1_occ25"].data.params["initial_occupancy"], "0.25")
        self.assertEqual(by_name["P2_hgb_proxy_h1_occ75"].data.params["initial_occupancy"], "0.75")
        summary_run = by_name[sensitivity.RUN_NAME]
        self.assertIn("val_f1_macro_boosting_occ25", summary_run.data.metrics)
        self.assertEqual(summary_run.data.metrics["eventos_recortados_occ25"], 10)
        self.assertEqual(client.search_registered_models(), [])

    def test_summary_contains_only_validation_metrics(self):
        tables = {0.5: risk_table()}
        summary = sensitivity.run_scenarios(
            tables, {0.5: {"clipped_events": 0}}, self.context, self.root / "figs2"
        )
        self.assertFalse([c for c in summary.columns if c.startswith("test_")])
        self.assertTrue(np.isfinite(summary["val_f1_macro"]).all())
        self.assertIsInstance(summary, pd.DataFrame)


if __name__ == "__main__":
    unittest.main()
