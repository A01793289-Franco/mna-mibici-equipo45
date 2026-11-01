import json
import subprocess

import pandas as pd
import pytest

from mibici import config as cfg
from mibici.dataset import normalize_trips
from mibici.security import scan_repository


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, check=True).stdout


def commit(root, name, content):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    git(root, "add", "--force", name)
    git(
        root,
        "-c",
        "user.name=Prueba",
        "-c",
        "user.email=prueba@example.invalid",
        "commit",
        "-m",
        "fixture",
    )


@pytest.fixture
def repository(tmp_path):
    git(tmp_path, "init")
    commit(tmp_path, "README.md", "Proyecto de prueba\n")
    return tmp_path


def test_clean_repository_and_history_pass(repository):
    commit(repository, ".env.example", "MLFLOW_TRACKING_URI=\n")
    result = scan_repository(repository, history=True)
    assert result["aprobado"]
    assert result["archivos_revisados"]["historicos"] >= 2


def test_deleted_secret_is_still_detected_in_history(repository):
    value = "pass" + "word = 'valor-privado-123'"
    commit(repository, "settings.py", value)
    commit(repository, "settings.py", "import os\n")
    assert scan_repository(repository)["aprobado"]
    result = scan_repository(repository, history=True)
    assert not result["aprobado"]
    assert result["hallazgos"][0]["origen"] == "historial"
    assert "valor-privado-123" not in json.dumps(result)


@pytest.mark.parametrize(
    "name", [".env", "data/raw/viajes.csv", "mlflow.db", "models/model.skops"]
)
def test_private_files_are_rejected_even_when_empty(repository, name):
    commit(repository, name, "")
    result = scan_repository(repository, history=True)
    assert not result["aprobado"]
    assert any(item["archivo"] == name for item in result["hallazgos"])


def test_ignored_local_secret_is_not_published(repository):
    commit(repository, ".gitignore", ".env\n")
    (repository / ".env").write_text("API" + "_KEY='valor-local-123'\n")
    assert scan_repository(repository, history=True)["aprobado"]


def test_deleted_private_file_is_detected(repository):
    commit(repository, "data/raw/viajes.csv", "id\n1\n")
    git(repository, "rm", "data/raw/viajes.csv")
    git(
        repository,
        "-c",
        "user.name=Prueba",
        "-c",
        "user.email=prueba@example.invalid",
        "commit",
        "-m",
        "elimina fixture",
    )
    result = scan_repository(repository, history=True)
    assert not result["aprobado"]
    assert any(item["origen"] == "historial" for item in result["hallazgos"])


@pytest.mark.parametrize("personal", ["email", "nombre", "usuario_id", "birth_year"])
def test_cleaned_trips_exclude_personal_columns(personal):
    frame = pd.DataFrame(
        {
            "trip_id": [1],
            "origin_id": [1],
            "destination_id": [2],
            "started_at": ["2026-01-02 08:00"],
            "ended_at": ["2026-01-02 08:10"],
            personal: ["dato de prueba"],
        }
    )
    clean, _ = normalize_trips(
        frame,
        pd.Timestamp("2026-01-01", tz=cfg.TIMEZONE),
        pd.Timestamp("2026-02-01", tz=cfg.TIMEZONE),
        set(),
    )
    assert len(clean) == 1
    assert personal not in clean.columns
    assert set(clean.columns) == {
        "trip_id",
        "origin_id",
        "destination_id",
        "started_at",
        "ended_at",
    }
