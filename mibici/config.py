"""Configuración acordada para la propuesta del equipo 45."""

from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = ROOT_DIR / "models"
FIGURES_DIR = ROOT_DIR / "reports" / "figures"
REFERENCES_DIR = ROOT_DIR / "references"
MANIFEST_PATH = REFERENCES_DIR / "data_manifest.json"
MLFLOW_DB = ROOT_DIR / "mlflow.db"
TRACKING_URI = f"sqlite:///{MLFLOW_DB.as_posix()}"

TEAM = "45"
EXPERIMENT_NAME = f"mibici-equipo{TEAM}"
SEED = 42
TIMEZONE = "America/Mexico_City"
DATA_PORTAL_URL = "https://www.mibici.net/es/datos-abiertos/"
STATIONS_URL = "https://www.mibici.net/site/assets/files/1118/nomenclatura_2026_09.csv"

START_DATE = date(2026, 1, 1)
TRAIN_END = date(2026, 7, 1)
VALIDATION_END = date(2026, 9, 1)
END_DATE_EXCLUSIVE = date(2026, 10, 1)

FREQUENCY = "1h"
HORIZON_HOURS = 1
LAGS_HOURS = (1, 24, 168)
ROLLING_HOURS = (24, 168)
SEASONAL_LAG_HOURS = 168

INITIAL_OCCUPANCY = 0.5
LOW_OCCUPANCY = 0.1
HIGH_OCCUPANCY = 0.9
P2_CLASS_NAMES = ("normal", "riesgo_sin_bicicletas", "riesgo_sin_anclajes")
P2_INITIAL_OCCUPANCY_CHECKS = (0.25, 0.5, 0.75)

N_CLUSTERS = 3
KMEANS_N_INIT = 10
PROFILE_HOURS = 24


def create_directories():
    """Crea las carpetas locales de la plantilla sin descargar datos."""
    for directory in (
        RAW_DIR,
        INTERIM_DIR,
        PROCESSED_DIR,
        MODELS_DIR,
        FIGURES_DIR,
        REFERENCES_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    create_directories()
    print(f"Carpetas preparadas. Experimento propuesto: {EXPERIMENT_NAME}")
