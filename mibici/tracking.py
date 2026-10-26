import json
import os
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd

from mibici import config as cfg


def verify_inputs():
    from mibici.dataset import verify_manifest
    from mibici.features import verify_features

    source = json.loads(cfg.MANIFEST_PATH.read_text(encoding="utf-8"))
    features = json.loads(cfg.FEATURE_MANIFEST_PATH.read_text(encoding="utf-8"))
    verify_manifest(source, cfg.DATA_DIR)
    verify_features(features, cfg.DATA_DIR, source["data_version"])


@contextmanager
def project_run():
    import mlflow

    run_id = os.environ.pop("MLFLOW_RUN_ID", None)
    if run_id and mlflow.active_run() is None:
        with mlflow.start_run(run_id=run_id):
            mlflow.set_tags({"equipo": cfg.TEAM, "stage_of_work": "project"})
            yield
    else:
        yield


def log_bundle(context, params, training=None, target=None):
    import mlflow

    for name in ("data_manifest.json", "feature_manifest.json"):
        path = cfg.REFERENCES_DIR / name
        if path.exists():
            mlflow.log_artifact(str(path), artifact_path="data")
    for path in (
        Path(cfg.__file__),
        cfg.ROOT_DIR / "mibici/train.py",
        cfg.ROOT_DIR / "mibici/project.py",
        cfg.ROOT_DIR / "requirements.txt",
        cfg.ROOT_DIR / "MLproject",
        cfg.ROOT_DIR / "python_env.yaml",
    ):
        if path.exists():
            mlflow.log_artifact(str(path), artifact_path="config")
    mlflow.log_dict(
        {"context": context, "parameters": {k: str(v) for k, v in params.items()}},
        "config/execution.json",
    )
    if training is not None:
        frame = training.copy(deep=False)
        dataset = mlflow.data.from_pandas(
            frame,
            source=str(cfg.FEATURE_MANIFEST_PATH),
            targets=target,
            name="training_station_features",
        )
        mlflow.log_input(
            dataset,
            context="training",
            tags={
                "data_version": context["data_version"],
                "feature_version": context["feature_version"],
            },
        )


def log_model_check(model, example):
    import mlflow

    record = {
        "columns": list(example.columns),
        "data": example.to_numpy().tolist(),
        "dtypes": {col: str(dtype) for col, dtype in example.dtypes.items()},
        "prediction": np.asarray(model.predict(example)).tolist(),
    }
    if hasattr(model, "predict_proba"):
        record["probabilities"] = np.asarray(model.predict_proba(example)).tolist()
    mlflow.log_dict(record, "config/model_check.json")


def check_registered_model(name, alias="champion"):
    import mlflow
    from mlflow.tracking import MlflowClient

    client = MlflowClient()
    version = client.get_model_version_by_alias(name, alias)
    uri = f"models:/{name}@{alias}"
    model = mlflow.sklearn.load_model(uri)
    path = client.download_artifacts(version.run_id, "config/model_check.json")
    record = json.loads(Path(path).read_text())
    frame = pd.DataFrame(record["data"], columns=record["columns"]).astype(record["dtypes"])
    prediction = np.asarray(model.predict(frame))
    np.testing.assert_allclose(prediction, record["prediction"], rtol=1e-12, atol=1e-12)
    if "probabilities" in record:
        np.testing.assert_allclose(
            model.predict_proba(frame), record["probabilities"], rtol=1e-12, atol=1e-12
        )
    return {
        "name": name,
        "alias": alias,
        "version": version.version,
        "run_id": version.run_id,
        "checked_rows": len(frame),
        "git_commit": version.tags.get("git_commit"),
        "data_version": version.tags.get("data_version"),
        "status": "passed",
    }
