"""Configuración acordada para la propuesta del equipo 45.

Centraliza rutas, fuentes, fechas de partición, semilla, horizonte, umbrales del proxy P2 y
columnas predictoras de P1-P3. Los módulos importan estos valores en lugar de repetirlos; el
hash de este archivo queda registrado en los manifiestos de datos y variables.
"""

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
REQUEST_HEADERS = {"User-Agent": "MiBiciEquipo45/1.0", "Accept": "text/html,text/csv,*/*"}
DOWNLOAD_TIMEOUT = (15, 120)
CHUNK_ROWS = 100_000
DATA_SCHEMA_VERSION = "1"
TRIPS_DIR = INTERIM_DIR / "trips"
STATIONS_FILE = INTERIM_DIR / "stations.parquet"
FEATURE_MANIFEST_PATH = REFERENCES_DIR / "feature_manifest.json"
FEATURE_FILES = {
    "p1": PROCESSED_DIR / "p1_hourly.parquet",
    "p2": PROCESSED_DIR / "p2_hourly.parquet",
    "p3_train": PROCESSED_DIR / "p3_train.parquet",
    "p3_val": PROCESSED_DIR / "p3_val.parquet",
    "p3_test": PROCESSED_DIR / "p3_test.parquet",
}

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
MIN_PROFILE_DAYS = 14
P3_FEATURE_COLUMNS = tuple(
    f"{kind}_{hour:02d}" for kind in ("weekday", "weekend") for hour in range(PROFILE_HOURS)
)
CALENDAR_FEATURES = ("hour", "weekday", "is_weekend", "month")
P1_FEATURE_COLUMNS = (
    *CALENDAR_FEATURES,
    *(f"departures_lag_{lag}" for lag in LAGS_HOURS),
    *(f"departures_mean_{window}" for window in ROLLING_HOURS),
)
NET_FLOW_LAGS_HOURS = (1, 24)
P2_FEATURE_COLUMNS = (
    *P1_FEATURE_COLUMNS,
    "virtual_occupancy",
    *(f"net_flow_lag_{lag}" for lag in NET_FLOW_LAGS_HOURS),
)


def data_path(path, data_dir=DATA_DIR):
    """Resuelve una ruta de datos centralizada para un directorio local alternativo.

    Conserva la parte relativa a ``DATA_DIR`` y la coloca bajo ``data_dir``, para que
    ``--data-dir`` reutilice la misma estructura sin modificar la configuración.
    """
    return Path(data_dir) / Path(path).relative_to(DATA_DIR)


def create_directories():
    """Crea las carpetas locales de la plantilla sin descargar datos.

    Prepara ``data/raw``, ``data/interim``, ``data/processed``, ``models``, ``reports/figures`` y
    ``references``; si ya existen, no hace nada.
    """
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
