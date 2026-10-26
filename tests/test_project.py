import contextlib
import io
from pathlib import Path
import unittest
from unittest import mock

import yaml

from mibici import config as cfg
from mibici import project, train


class TestProject(unittest.TestCase):
    def test_config_defaults_are_resolved_without_repeating_seed(self):
        args = project.parser().parse_args(["train", "--question", "p1"])
        with mock.patch.object(cfg, "SEED", 321):
            values = project.training_arguments(args)
        self.assertEqual(values[values.index("--seed") + 1], "321")
        self.assertNotIn("--final-test", values)
        self.assertNotIn("--tune", values)

    def test_single_model_does_not_promote_without_explicit_request(self):
        args = project.parser().parse_args(["train", "--question", "p2", "--model", "persistence"])
        self.assertIn("--no-register", project.training_arguments(args))
        args.register = "true"
        self.assertNotIn("--no-register", project.training_arguments(args))
        args.final_test = "false"
        self.assertNotIn("--final-test", project.training_arguments(args))
        args.final_test = "true"
        self.assertIn("--final-test", project.training_arguments(args))

    def test_invalid_boolean_is_rejected(self):
        with self.assertRaises(ValueError):
            project.boolean("yes")

    def test_incompatible_models_fail_before_reading_data(self):
        for arguments in (
            ["--question", "p1", "--model", "ward"],
            ["--question", "p3", "--learning-rate", "0.1"],
            ["--question", "p2", "--model", "logistic", "--max-leaf-nodes", "7"],
            ["--question", "p1", "--learning-rate", "nan"],
            ["--question", "p1", "--seed", "-1"],
            ["--question", "p1", "--model", "hgb", "--tune"],
        ):
            with (
                self.subTest(arguments=arguments),
                mock.patch.object(train, "verify_inputs") as verify,
            ):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    train.main(arguments)
                verify.assert_not_called()

    def test_logistic_parameters_reach_runner_and_estimator(self):
        with (
            mock.patch.object(train, "verify_inputs"),
            mock.patch.object(train, "configure_mlflow"),
            mock.patch.object(
                train, "run_context", return_value={"git_commit": "abc", "git_dirty": "false"}
            ),
            mock.patch.dict(train.RUNNERS, {"P2": mock.Mock()}),
        ):
            project.main(
                [
                    "train",
                    "--question",
                    "p2",
                    "--model",
                    "logistic",
                    "--c",
                    "0.5",
                    "--max-iter",
                    "50",
                    "--seed",
                    "123",
                ]
            )
            kwargs = train.RUNNERS["P2"].call_args.kwargs
        self.assertEqual(kwargs["model_params"], {"C": 0.5, "max_iter": 50})
        self.assertFalse(kwargs["register"])
        model = train.make_risk_baseline(**kwargs["model_params"], random_state=kwargs["seed"])
        self.assertEqual(model.steps[-1][1].C, 0.5)
        self.assertEqual(model.steps[-1][1].random_state, 123)

    def test_project_declares_both_entries_and_pinned_environment(self):
        root = Path(cfg.ROOT_DIR)
        spec = yaml.safe_load((root / "MLproject").read_text())
        environment = yaml.safe_load((root / spec["python_env"]).read_text())
        self.assertEqual(environment["dependencies"], ["-r requirements.txt"])
        self.assertEqual(str(environment["python"]), "3.13.15")
        self.assertIn("ingest", spec["entry_points"])
        parameters = spec["entry_points"]["train"]["parameters"]
        for key in ("seed", "learning_rate", "max_iter", "max_leaf_nodes", "n_clusters"):
            self.assertEqual(parameters[key]["default"], "config")


if __name__ == "__main__":
    unittest.main()
