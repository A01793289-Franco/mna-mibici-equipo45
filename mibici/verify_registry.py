import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import davies_bouldin_score, silhouette_score

from mibici import config as cfg
from mibici.predict import load_champion
from mibici.tracking import check_registered_model, verify_inputs
from mibici.train import (
    REGISTERED_MODELS,
    classification_metrics,
    configure_mlflow,
    regression_metrics,
)


def verify(question, alias="champion", evaluate=True):
    import mlflow

    record = check_registered_model(REGISTERED_MODELS[question], alias)
    if not evaluate:
        return record
    model, columns = load_champion(question, alias)
    client = mlflow.tracking.MlflowClient()
    source = client.get_run(record["run_id"])
    if (
        source.data.params["data_version"]
        != json.loads(cfg.MANIFEST_PATH.read_text())["data_version"]
    ):
        raise ValueError("La versión de datos del modelo no coincide con los datos locales")
    if (
        source.data.params["feature_version"]
        != json.loads(cfg.FEATURE_MANIFEST_PATH.read_text())["feature_version"]
    ):
        raise ValueError(
            "La versión de variables del modelo no coincide con las variables locales"
        )
    if question == "P3":
        frame = pd.read_parquet(cfg.FEATURE_FILES["p3_val"])
        prediction = model.predict(frame[columns])
        record["validation_rows"] = len(frame)
        record["groups_assigned"] = len(np.unique(prediction))
        metrics = {}
        if 1 < len(np.unique(prediction)) < len(frame):
            metrics = {
                "val_assignment_silhouette": silhouette_score(frame[columns], prediction),
                "val_assignment_davies_bouldin": davies_bouldin_score(frame[columns], prediction),
            }
            for key, value in metrics.items():
                np.testing.assert_allclose(value, source.data.metrics[key], rtol=1e-10, atol=1e-10)
        record["metrics"] = metrics
        return record
    frame = pd.read_parquet(cfg.FEATURE_FILES[question.lower()])
    frame = frame[frame["split"] == "val"]
    prediction = model.predict(frame[columns])
    if question == "P1":
        metrics = regression_metrics(frame["target_departures"], prediction, "val")
    else:
        metrics, _ = classification_metrics(
            frame["target_risk"], prediction, model.predict_proba(frame[columns]), "val"
        )
    for key, value in metrics.items():
        np.testing.assert_allclose(value, source.data.metrics[key], rtol=1e-10, atol=1e-10)
    record.update({"validation_rows": len(frame), "metrics": metrics})
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Comprueba los modelos registrados sin usar prueba"
    )
    parser.add_argument("--question", choices=[*REGISTERED_MODELS, "all"], default="all")
    parser.add_argument("--alias", default="champion")
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not args.smoke_only:
        verify_inputs()
    configure_mlflow()
    questions = REGISTERED_MODELS if args.question == "all" else [args.question]
    records = [verify(q, args.alias, not args.smoke_only) for q in questions]
    text = json.dumps(records, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8", newline="\n")
    print(text)


if __name__ == "__main__":
    main()
