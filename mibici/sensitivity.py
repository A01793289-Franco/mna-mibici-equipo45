"""Sensibilidad de P2 a la ocupación inicial del proxy (25%, 50% y 75%).

Uso desde la raíz del repositorio, con los datos ya ingeridos y las variables ya construidas::

    python -m mibici.sensitivity
    python -m mibici.sensitivity --values 0.25 0.75

La etiqueta de P2 sale de una ocupación virtual que parte de un supuesto arbitrario (``0.5`` de la
capacidad). Este módulo repite P2 con otros valores iniciales para ver si las conclusiones cambian.

A diferencia de ``python -m mibici.features --initial-occupancy``, **no escribe nada en ``data/`` ni
en los manifiestos**: recalcula la tabla de P2 en memoria con ``features.p2_features`` (la misma
función que usa la construcción de variables), la compara con la tabla guardada cuando el escenario
es el valor por defecto, entrena los tres modelos de P2 y registra cada uno como un run de MLflow
con ``initial_occupancy`` y un sufijo ``_occ25``, ``_occ50``, ``_occ75``. Solo usa validación, no
registra modelos en el Model Registry y no abre septiembre.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib
import pandas as pd

from mibici import config as cfg
from mibici.dataset import sha256_file
from mibici.features import hourly_counts, load_events, p2_features, verify_features
from mibici.train import (
    HORIZON_LABEL,
    configure_mlflow,
    run_context,
    run_p2,
    run_tags,
)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SCENARIOS = tuple(cfg.P2_INITIAL_OCCUPANCY_CHECKS)
MODELS = {
    "persistencia_proxy": "Persistencia",
    "logistica_proxy": "Logística",
    "hgb_proxy": "Boosting",
}
SENSITIVITY_DIR = cfg.FIGURES_DIR / "sensibilidad"
RUN_NAME = "P2_sensibilidad_ocupacion_inicial"


def suffix(initial):
    """Sufijo de nombre de run: 0.25 -> ``_occ25``."""
    return f"_occ{round(initial * 100):02d}"


def load_inputs(data_dir=cfg.DATA_DIR, manifest_path=cfg.MANIFEST_PATH):
    """Carga los insumos de ``p2_features`` tras verificar los archivos que se leen.

    Comprueba el SHA-256 de los Parquet limpios del manifiesto y el manifiesto de variables (código,
    configuración y tabla P1). No requiere los CSV originales.
    """
    source = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    for item in [*source["trips"], source["stations"]]:
        path = Path(data_dir) / item["clean_path"]
        if not path.is_file() or sha256_file(path) != item["clean_sha256"]:
            raise ValueError(f"Archivo ausente o modificado: {path}")
    verify_features(
        json.loads(cfg.FEATURE_MANIFEST_PATH.read_text(encoding="utf-8")),
        data_dir,
        source["data_version"],
    )
    print("Cargando eventos...", flush=True)
    events = load_events(source, data_dir)
    return {
        "events": events,
        "hourly": hourly_counts(events, source["start"], source["end_exclusive"]),
        "stations": pd.read_parquet(Path(data_dir) / source["stations"]["clean_path"]),
        "p1": pd.read_parquet(cfg.data_path(cfg.FEATURE_FILES["p1"], data_dir)),
    }


def scenario_table(inputs, initial):
    """Tabla de P2 en memoria para una ocupación inicial; regresa ``(tabla, diagnósticos)``."""
    return p2_features(
        inputs["p1"], inputs["hourly"], inputs["events"], inputs["stations"], initial
    )


def check_matches_saved(table, data_dir=cfg.DATA_DIR):
    """Comprueba que la tabla en memoria con la ocupación por defecto es idéntica a la guardada."""
    saved = pd.read_parquet(cfg.data_path(cfg.FEATURE_FILES["p2"], data_dir))
    pd.testing.assert_frame_equal(table, saved, check_exact=True)


def class_shares(table):
    """Proporción de cada clase de riesgo por partición (entrenamiento y validación)."""
    rows = {}
    for split in ("train", "val"):
        part = table[table["split"] == split]["target_risk"]
        for label, name in enumerate(cfg.P2_CLASS_NAMES):
            rows[f"{split}_{name}"] = float((part == label).mean())
    return rows


def summarize(results, shares, diagnostics):
    """Tabla con una fila por escenario y modelo: métricas, proporción de clases y recortes."""
    rows = []
    for initial in SCENARIOS:
        if initial not in results:
            continue
        for key, label in MODELS.items():
            metrics = results[initial][f"P2_{key}_{HORIZON_LABEL}{suffix(initial)}"]
            rows.append(
                {
                    "ocupacion_inicial": initial,
                    "modelo": label,
                    "val_f1_macro": metrics["val_f1_macro"],
                    "val_balanced_accuracy": metrics["val_balanced_accuracy"],
                    **shares[initial],
                    "eventos_recortados": diagnostics[initial]["clipped_events"],
                }
            )
    return pd.DataFrame(rows)


def plot_summary(table, path):
    """F1 macro por escenario y modelo, y distribución de clases en entrenamiento."""
    fig, (ax_f1, ax_cls) = plt.subplots(1, 2, figsize=(13, 4.5))
    wide = table.pivot(index="ocupacion_inicial", columns="modelo", values="val_f1_macro")
    wide = wide[[label for label in MODELS.values() if label in wide.columns]]
    wide.plot.bar(ax=ax_f1, rot=0)
    ax_f1.set(
        title="F1 macro en validación por ocupación inicial",
        xlabel="Ocupación inicial",
        ylabel="F1 macro",
        ylim=(0, 1.2),
    )
    ax_f1.legend(ncol=3, loc="upper center", fontsize=8, title=None)
    shares = table.drop_duplicates("ocupacion_inicial").set_index("ocupacion_inicial")
    shares[[f"train_{name}" for name in cfg.P2_CLASS_NAMES]].rename(
        columns=lambda column: column.removeprefix("train_")
    ).plot.bar(stacked=True, ax=ax_cls, rot=0)
    ax_cls.set(
        title="Distribución de clases en entrenamiento",
        xlabel="Ocupación inicial",
        ylabel="Proporción",
        ylim=(0, 1.2),
    )
    ax_cls.legend(ncol=3, loc="upper center", fontsize=8)
    fig.tight_layout()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def run_scenarios(tables, diagnostics, context, figures_dir=SENSITIVITY_DIR):
    """Entrena y registra P2 en cada escenario y un run resumen con la tabla y la figura.

    ``tables`` y ``diagnostics`` son diccionarios ``{ocupacion_inicial: ...}``. Regresa la tabla
    resumen.
    """
    import mlflow

    results = {}
    for initial, table in tables.items():
        print(f"\n##### Ocupación inicial {initial} #####", flush=True)
        results[initial] = run_p2(
            table,
            figures_dir=figures_dir,
            context=context,
            register=False,
            initial_occupancy=initial,
            suffix=suffix(initial),
        )
    shares = {initial: class_shares(table) for initial, table in tables.items()}
    summary = summarize(results, shares, diagnostics)
    figures_dir = Path(figures_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)
    csv = figures_dir / "p2_sensibilidad_ocupacion_inicial.csv"
    summary.to_csv(csv, index=False)
    figure = plot_summary(summary, figures_dir / "p2_sensibilidad_ocupacion_inicial.png")
    with mlflow.start_run(run_name=RUN_NAME):
        mlflow.set_tags(run_tags("P2", "sensibilidad", context))
        mlflow.log_params(
            {
                "ocupaciones_iniciales": ",".join(str(value) for value in tables),
                "por_defecto": cfg.INITIAL_OCCUPANCY,
                "seed": cfg.SEED,
            }
        )
        for row in summary.to_dict("records"):
            tag = f"{row['modelo'].lower()}_occ{round(row['ocupacion_inicial'] * 100):02d}"
            for metric in ("val_f1_macro", "val_balanced_accuracy"):
                if math.isfinite(row[metric]):
                    mlflow.log_metric(f"{metric}_{tag}", row[metric])
        for initial, values in shares.items():
            for name, value in values.items():
                mlflow.log_metric(f"proporcion_{name}_occ{round(initial * 100):02d}", value)
            mlflow.log_metric(
                f"eventos_recortados_occ{round(initial * 100):02d}",
                diagnostics[initial]["clipped_events"],
            )
        mlflow.log_artifact(str(figure), artifact_path="figuras")
        mlflow.log_artifact(str(csv), artifact_path="tablas")
    print("\n=== P2: sensibilidad a la ocupación inicial ===", flush=True)
    print(summary.round(4).to_string(index=False), flush=True)
    return summary


def main(argv=None):
    """Recalcula P2 con distintas ocupaciones iniciales y registra los runs."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--values",
        type=float,
        nargs="+",
        default=list(SCENARIOS),
        help="ocupaciones iniciales entre 0 y 1 (por defecto 0.25 0.5 0.75)",
    )
    args = parser.parse_args(argv)
    configure_mlflow()
    context = run_context()
    inputs = load_inputs()
    tables, diagnostics = {}, {}
    for initial in args.values:
        print(f"Construyendo P2 con ocupación inicial {initial}...", flush=True)
        tables[initial], diagnostics[initial] = scenario_table(inputs, initial)
        if initial == cfg.INITIAL_OCCUPANCY:
            check_matches_saved(tables[initial])
            print("La tabla en memoria coincide con la guardada.", flush=True)
    run_scenarios(tables, diagnostics, context)
    print("\nListo. Ninguna tabla ni manifiesto se modificó.")


if __name__ == "__main__":
    main()
