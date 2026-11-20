import json
import shutil

import mlflow
import pytest

from mibici import registry_bundle as bundle
from mibici import train
from tests.compose_seed import seed_bundle


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    root = tmp_path_factory.mktemp("serving-export")
    destination = root / "bundle"
    seed_bundle(destination)
    return destination


def test_import_survives_removal_of_source_registry_and_repeated_start(exported, tmp_path):
    train.configure_mlflow(
        tracking_uri=f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}",
        artifact_root=tmp_path / "artifacts",
        experiment="compose-import-test",
    )
    first = bundle.import_bundle(exported)
    second = bundle.import_bundle(exported)
    assert first == second
    client = mlflow.tracking.MlflowClient()
    for question, name in bundle.NAMES.items():
        versions = client.search_model_versions(f"name='{name}'")
        assert len(versions) == 1
        assert str(client.get_model_version_by_alias(name, "champion").version) == "1"
        record = bundle.validate_bundle(exported)["models"][question]["check"]
        bundle.check_model(f"models:/{name}@champion", record)


@pytest.mark.parametrize("change", ["changed", "missing", "extra"])
def test_invalid_hashes_are_rejected_before_registry_access(
    exported, tmp_path, monkeypatch, change
):
    destination = tmp_path / "bundle"
    shutil.copytree(exported, destination)
    model = destination / "P1" / "MLmodel"
    if change == "changed":
        model.write_text(model.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    elif change == "missing":
        model.unlink()
    else:
        (destination / "extra.txt").write_text("extra", encoding="utf-8")

    def unexpected():
        pytest.fail("No debe contactar el Registry si el paquete está alterado")

    monkeypatch.setattr(bundle, "MlflowClient", unexpected)
    with pytest.raises(ValueError, match="SHA-256"):
        bundle.import_bundle(destination)


def test_incorrect_model_names_are_rejected(exported, tmp_path):
    destination = tmp_path / "bundle"
    shutil.copytree(exported, destination)
    manifest_path = destination / "bundle.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["models"]["P1"]["name"] = "otro-modelo"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="Nombre"):
        bundle.validate_bundle(destination)


def test_existing_champion_from_another_bundle_is_preserved(exported, tmp_path):
    train.configure_mlflow(
        tracking_uri=f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}",
        artifact_root=tmp_path / "artifacts",
        experiment="compose-conflict-test",
    )
    bundle.import_bundle(exported)
    client = mlflow.tracking.MlflowClient()
    name = bundle.NAMES["P1"]
    client.set_model_version_tag(name, "1", "serving_bundle_sha256", "other")
    with pytest.raises(ValueError, match="no se sobrescribe"):
        bundle.import_bundle(exported)
    assert str(client.get_model_version_by_alias(name, "champion").version) == "1"
    assert len(client.search_model_versions(f"name='{name}'")) == 1


def test_export_never_replaces_an_existing_directory(exported):
    before = bundle.file_hash(exported / "bundle.json")
    with pytest.raises(ValueError, match="ya existe"):
        bundle.export_bundle(exported)
    assert bundle.file_hash(exported / "bundle.json") == before


def test_symlinks_are_rejected(exported, tmp_path):
    destination = tmp_path / "bundle"
    shutil.copytree(exported, destination)
    link = destination / "linked"
    try:
        link.symlink_to(destination / "P1" / "MLmodel")
    except OSError:
        pytest.skip("El sistema no permite crear symlinks")
    with pytest.raises(ValueError, match="simbólicos"):
        bundle.validate_bundle(destination)
