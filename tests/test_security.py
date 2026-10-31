"""Controles básicos de seguridad: secretos, .env, dependencias fijadas y entradas de la API.

Complementan los análisis de CI (``pip-audit`` y ``bandit``) con reglas propias del proyecto.
"""

from pathlib import Path
import re
import shutil
import subprocess
from unittest import mock

from fastapi.testclient import TestClient
import pytest

from mibici import api
from mibici import config as cfg

ROOT = Path(cfg.ROOT_DIR)
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".toml",
    ".cfg",
    ".yaml",
    ".yml",
    ".json",
    ".ipynb",
    ".example",
    "",
}
SECRET_PATTERNS = {
    "llave privada": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "llave de AWS": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "token de GitHub": re.compile(r"\b(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{30,}|github_pat_\w{40,}"),
    "credencial asignada": re.compile(
        r"(?i)\b(?:password|passwd|secret|api_?key|access_?token)\b\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"
    ),
    "URL con usuario y contraseña": re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@"),
}

git = pytest.mark.skipif(shutil.which("git") is None, reason="requiere git")


def git_output(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)


# ---------------------------------------------------------------------------
# Secretos y archivos .env
# ---------------------------------------------------------------------------
@git
@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".env.local",
        "mlflow.db",
        "mlflow.db-journal",
        "mlartifacts/m-1/model.pkl",
        "data/raw/viajes.csv",
        "data/processed/p1_hourly.parquet",
        "models/modelo.joblib",
    ],
)
def test_local_secrets_data_and_models_are_ignored(path):
    assert git_output("check-ignore", "--no-index", "-q", path).returncode == 0, path


@git
def test_env_example_is_versioned_and_not_ignored():
    assert git_output("check-ignore", "--no-index", "-q", ".env.example").returncode == 1


def test_env_example_has_no_values_and_only_variables_the_code_reads():
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    variables = dict(
        line.split("=", 1) for line in lines if line.strip() and not line.startswith("#")
    )
    assert variables == {"MLFLOW_TRACKING_URI": ""}
    code = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "mibici").glob("*.py"))
    for name in variables:
        assert name in code, f"{name} no se usa en mibici/"


@git
def test_repository_files_do_not_contain_credentials():
    """Revisa los archivos versionados y los nuevos aún sin añadir que .gitignore no excluye."""
    files = git_output("ls-files", "--cached", "--others", "--exclude-standard", "-z")
    files = files.stdout.split("\0")
    findings = []
    for name in filter(None, files):
        path = ROOT / name
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
            continue
        if path.stat().st_size > 5_000_000:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        findings += [f"{name}: {kind}" for kind, rx in SECRET_PATTERNS.items() if rx.search(text)]
    assert not findings, findings


# Los ejemplos se arman por partes para que este archivo no contenga el texto literal que la
# prueba anterior busca en el repositorio.
@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("pass" + "word = 'S3cr3t-valor'", "credencial asignada"),
        ("API" + '_KEY: "abcd1234efgh"', "credencial asignada"),
        ("postgresql://usuario:" + "clave@servidor/db", "URL con usuario y contraseña"),
        ("-----BEGIN RSA " + "PRIVATE KEY-----", "llave privada"),
    ],
)
def test_secret_patterns_detect_known_examples(text, kind):
    """Control del detector: sin esto, la prueba anterior podría pasar por patrones rotos."""
    assert SECRET_PATTERNS[kind].search(text)


@pytest.mark.parametrize(
    "text",
    ["tracking_uri = os.environ.get('MLFLOW_TRACKING_URI')", "https://www.mibici.net/datos"],
)
def test_secret_patterns_ignore_normal_code(text):
    assert not any(rx.search(text) for rx in SECRET_PATTERNS.values())


# ---------------------------------------------------------------------------
# Dependencias
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", ["requirements.txt", "requirements-validation.txt"])
def test_dependencies_are_pinned_to_exact_versions(name):
    loose = []
    for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line and not line.startswith(("-e ", "-r ")) and "==" not in line:
            loose.append(line)
    assert not loose, f"Dependencias sin versión exacta en {name}: {loose}"


# ---------------------------------------------------------------------------
# Validación de entradas de la API (complementa tests/test_api.py)
# ---------------------------------------------------------------------------
@pytest.fixture
def client():
    return TestClient(api.app, raise_server_exceptions=False)


PAYLOAD = {"question": "P1", "station_id": 1, "timestamp": "2026-08-15T08:00"}


@pytest.mark.parametrize(
    "changes",
    [
        {"station_id": 0},
        {"station_id": 2**31},
        {"station_id": 2**63},
        {"station_id": 10**30},
        {"station_id": 1.5},
        {"station_id": True},
        {"station_id": None},
        {"question": "p1"},
        {"question": "P1' OR '1'='1"},
        {"question": "P1" * 10_000},
        {"timestamp": ""},
        {"timestamp": "2026-13-45T08:00"},
    ],
    ids=lambda changes: f"{next(iter(changes))}={str(next(iter(changes.values())))[:20]}",
)
def test_invalid_or_extreme_inputs_are_rejected_before_loading_models(client, changes):
    with mock.patch.object(api, "load_champion") as load:
        response = client.post("/predict", json={**PAYLOAD, **changes})
    assert response.status_code == 422
    load.assert_not_called()


@pytest.mark.parametrize("body", [b"", b"no es json", b"[]", b'{"question": "P1"}'])
def test_malformed_bodies_return_422(client, body):
    response = client.post("/predict", content=body, headers={"content-type": "application/json"})
    assert response.status_code == 422


def test_largest_valid_station_id_does_not_crash(client):
    with (
        mock.patch.object(api, "configure_mlflow"),
        mock.patch.object(api, "load_champion", return_value=(mock.Mock(), ["hour"])),
        mock.patch.object(api.pd, "read_parquet", return_value=api.pd.DataFrame()),
    ):
        response = client.post("/predict", json={**PAYLOAD, "station_id": api.MAX_STATION_ID})
    assert response.status_code == 404


def test_server_errors_do_not_expose_internal_details(client):
    with (
        mock.patch.object(api, "configure_mlflow"),
        mock.patch.object(
            api, "load_champion", side_effect=api.PredictionError(r"C:\ruta\interna\mlflow.db")
        ),
    ):
        response = client.post("/predict", json=PAYLOAD)
    assert response.status_code == 503
    assert "ruta" not in response.text and "mlflow.db" not in response.text
