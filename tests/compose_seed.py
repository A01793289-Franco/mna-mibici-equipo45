import argparse
from pathlib import Path
import tempfile

import mlflow
import pandas as pd

from mibici import config as cfg
from mibici import train
from mibici.deployable import PersistenceRisk, SeasonalDemand
from mibici.registry_bundle import export_bundle
from mibici.verify_api import P1_EXAMPLE, P2_EXAMPLE


def seed_bundle(directory):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        train.configure_mlflow(
            tracking_uri=f"sqlite:///{(root / 'mlflow.db').as_posix()}",
            artifact_root=root / "artifacts",
            experiment="compose-ci-synthetic",
        )
        frames = {
            "P1": pd.DataFrame([P1_EXAMPLE] * 3)[["station_id", *cfg.P1_FEATURE_COLUMNS]],
            "P2": pd.DataFrame([P2_EXAMPLE] * 3)[list(cfg.P2_FEATURE_COLUMNS)],
        }
        frames["P2"]["virtual_occupancy"] = [0.05, 0.5, 0.95]
        models = {
            "P1": SeasonalDemand().fit(frames["P1"], [2.0, 3.0, 4.0]),
            "P2": PersistenceRisk().fit(frames["P2"]),
        }
        client = mlflow.tracking.MlflowClient()
        for question, model in models.items():
            with mlflow.start_run(run_name=f"CI_{question}") as run:
                mlflow.set_tag("dataset_kind", "synthetic_ci_only")
                info = train.log_model(model, frames[question])
                version = mlflow.register_model(info.model_uri, train.REGISTERED_MODELS[question])
                client.set_registered_model_alias(version.name, "champion", version.version)
                if run.info.run_id != version.run_id:
                    raise ValueError("El modelo de prueba no conserva su run")
        return export_bundle(directory)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Paquete sintético exclusivo para CI")
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    seed_bundle(args.directory)
