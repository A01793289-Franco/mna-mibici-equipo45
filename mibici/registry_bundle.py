import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

import mlflow
import numpy as np
import pandas as pd
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient

from mibici.train import REGISTERED_MODELS

NAMES = {question: REGISTERED_MODELS[question] for question in ("P1", "P2")}


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(directory):
    paths = sorted(directory.rglob("*"))
    if any(path.is_symlink() for path in paths):
        raise ValueError("El paquete no admite enlaces simbólicos")
    return {
        path.relative_to(directory).as_posix(): file_hash(path)
        for path in paths
        if path.is_file() and path != directory / "bundle.json"
    }


def validate_bundle(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "bundle.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or set(manifest.get("models", {})) != set(NAMES):
        raise ValueError("Se requiere un paquete con los modelos P1 y P2")
    if manifest.get("files") != inventory(directory):
        raise ValueError("El contenido del paquete no coincide con sus hashes SHA-256")
    for question, name in NAMES.items():
        record = manifest["models"][question]
        if record.get("name") != name or not (directory / question / "MLmodel").is_file():
            raise ValueError(f"Nombre o artefactos inválidos para {question}")
    return manifest


def check_model(uri, record):
    model = mlflow.sklearn.load_model(uri)
    frame = pd.DataFrame(record["data"], columns=record["columns"]).astype(record["dtypes"])
    signature = mlflow.models.get_model_info(uri).signature
    if signature is None or signature.inputs.input_names() != record["columns"]:
        raise ValueError("La firma del modelo no coincide con la prueba de reproducción")
    np.testing.assert_allclose(model.predict(frame), record["prediction"], rtol=1e-12, atol=1e-12)
    if "probabilities" in record:
        np.testing.assert_allclose(
            model.predict_proba(frame), record["probabilities"], rtol=1e-12, atol=1e-12
        )


def export_bundle(directory):
    directory = Path(directory)
    if directory.exists():
        raise ValueError(f"El destino ya existe: {directory}; utiliza otra carpeta")
    client = MlflowClient()
    manifest = {"schema_version": 1, "models": {}}
    directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=directory.parent) as temporary:
        staging = Path(temporary)
        for question, name in NAMES.items():
            version = client.get_model_version_by_alias(name, "champion")
            uri = f"models:/{name}/{version.version}"
            with tempfile.TemporaryDirectory() as download:
                source = mlflow.artifacts.download_artifacts(artifact_uri=uri, dst_path=download)
                shutil.copytree(source, staging / question)
                metadata_path = staging / question / "MLmodel"
                metadata = mlflow.models.Model.load(str(metadata_path))
                metadata.model_id = None
                metadata.save(str(metadata_path))
                record_path = client.download_artifacts(
                    version.run_id, "config/model_check.json", dst_path=download
                )
                record = json.loads(Path(record_path).read_text(encoding="utf-8"))
            check_model(str(staging / question), record)
            run = client.get_run(version.run_id)
            tags = {
                key: run.data.tags[key]
                for key in ("git_commit", "data_version", "feature_version", "dataset_kind")
                if key in run.data.tags
            }
            manifest["models"][question] = {
                "name": name,
                "source_version": version.version,
                "source_run_id": version.run_id,
                "tags": tags,
                "check": record,
            }
        manifest["files"] = inventory(staging)
        (staging / "bundle.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        validate_bundle(staging)
        shutil.move(str(staging), str(directory))
    return manifest


def import_bundle(directory):
    directory = Path(directory)
    manifest = validate_bundle(directory)
    bundle_hash = file_hash(directory / "bundle.json")
    client = MlflowClient()
    existing = {}
    for question, name in NAMES.items():
        check_model(str(directory / question), manifest["models"][question]["check"])
        try:
            version = client.get_model_version_by_alias(name, "champion")
        except MlflowException as error:
            if error.error_code != "RESOURCE_DOES_NOT_EXIST":
                raise
        else:
            if version.tags.get("serving_bundle_sha256") != bundle_hash:
                raise ValueError(f"{name}@champion ya existe con otro paquete; no se sobrescribe")
            existing[question] = version
    mlflow.set_experiment("mibici-equipo45-serving")
    imported = {}
    for question, name in NAMES.items():
        record = manifest["models"][question]
        if question in existing:
            version = existing[question]
        else:
            with mlflow.start_run(run_name=f"import_{question}") as run:
                mlflow.set_tags({**record["tags"], "stage_of_work": "serving_import"})
                mlflow.log_params(
                    {key: record[key] for key in ("source_run_id", "source_version")}
                )
                mlflow.log_artifacts(str(directory / question), artifact_path="model")
                mlflow.log_dict(record["check"], "config/model_check.json")
                mlflow.log_dict(manifest, "config/serving_bundle.json")
                version = mlflow.register_model(f"runs:/{run.info.run_id}/model", name)
            client.set_model_version_tag(
                name, version.version, "serving_bundle_sha256", bundle_hash
            )
        uri = f"models:/{name}/{version.version}"
        check_model(uri, record["check"])
        imported[question] = {"name": name, "version": version.version}
    for question, record in imported.items():
        client.set_registered_model_alias(record["name"], "champion", record["version"])
    return {"bundle_sha256": bundle_hash, "models": imported}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Traslada P1/P2 del Registry a Compose")
    parser.add_argument("command", choices=["export", "import"])
    parser.add_argument("--directory", type=Path, default=Path("models/serving"))
    args = parser.parse_args(argv)
    operation = export_bundle if args.command == "export" else import_bundle
    try:
        result = operation(args.directory)
    except (ValueError, OSError, MlflowException) as error:
        parser.exit(1, f"Error: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
