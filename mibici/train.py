"""Entrenamiento, evaluación y registro en MLflow de P1, P2 y P3.

Uso desde la raíz del repositorio::

    python -m mibici.train --question P1
    python -m mibici.train --question all
    python -m mibici.train --question all --final-test   # evaluación final sobre septiembre

Cada modelo es un run del experimento ``config.EXPERIMENT_NAME``. Los nombres siguen la propuesta
(``P1_estacional_h1``, ``P2_logistica_proxy_h1``, ``P3_kmeans_perfil48``...). Rutas, fechas,
semilla, columnas predictoras y número de grupos salen de ``mibici/config.py``.

Por defecto solo se evalúa en validación. La prueba (septiembre) se usa una única vez, al final,
con ``--final-test``, para no elegir decisiones mirando ese conjunto.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess

import matplotlib
import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    adjusted_rand_score,
    average_precision_score,
    balanced_accuracy_score,
    davies_bouldin_score,
    f1_score,
    mean_absolute_error,
    precision_recall_fscore_support,
    r2_score,
    root_mean_squared_error,
    silhouette_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from mibici import config as cfg

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

P1_TARGET = "target_departures"
P2_TARGET = "target_risk"
P2_CLASSES = (0, 1, 2)
HORIZON_LABEL = f"h{cfg.HORIZON_HOURS}"


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------
def wape(y_true, y_pred):
    """WAPE global: suma del error absoluto entre la demanda observada total.

    Se usa en lugar de MAPE porque hay muchas horas sin viajes. Si la demanda total es cero,
    la métrica no está definida y se regresa NaN.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denominator = np.abs(y_true).sum()
    if denominator == 0:
        return float("nan")
    return float(np.abs(y_true - y_pred).sum() / denominator)


def regression_metrics(y_true, y_pred, prefix):
    """MAE (principal), RMSE y WAPE de la propuesta, más R² como referencia."""
    return {
        f"{prefix}_mae": float(mean_absolute_error(y_true, y_pred)),
        f"{prefix}_rmse": float(root_mean_squared_error(y_true, y_pred)),
        f"{prefix}_wape": wape(y_true, y_pred),
        f"{prefix}_r2": float(r2_score(y_true, y_pred)),
    }


def classification_metrics(y_true, y_pred, proba, prefix):
    """F1 macro (principal), balanced accuracy, precisión/recall por clase y AP uno-contra-resto.

    ``proba`` debe tener una columna por clase en el orden de ``P2_CLASSES``. Si una clase no
    aparece en los datos evaluados, su AP no está definido: no se inventa un cero y se reporta en
    la segunda salida.
    """
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    names = cfg.P2_CLASS_NAMES
    labels = list(P2_CLASSES)
    metrics = {
        f"{prefix}_f1_macro": float(
            f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)
        ),
        f"{prefix}_balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
    }
    precision, recall, _, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0
    )
    undefined, averages = [], []
    for index, label in enumerate(labels):
        metrics[f"{prefix}_precision_{names[label]}"] = float(precision[index])
        metrics[f"{prefix}_recall_{names[label]}"] = float(recall[index])
        positives = y_true == label
        if positives.any():
            average = float(average_precision_score(positives, proba[:, index]))
            metrics[f"{prefix}_ap_{names[label]}"] = average
            averages.append(average)
        else:
            undefined.append(f"{prefix}_ap_{names[label]}")
    if averages:
        metrics[f"{prefix}_ap_macro"] = float(np.mean(averages))
    else:
        undefined.append(f"{prefix}_ap_macro")
    return metrics, undefined


# ---------------------------------------------------------------------------
# P1: baseline estacional y modelo candidato
# ---------------------------------------------------------------------------
def weekly_baseline(train, frame):
    """Misma estación y misma hora de la semana anterior.

    Sin historia se usa el promedio de esa estación, día y hora aprendido solo en entrenamiento
    y, para una estación no vista, el promedio global de entrenamiento (como indica la propuesta).
    """
    prediction = frame["departures_lag_168"].astype(float)
    if prediction.isna().any():
        keys = ["station_id", "weekday", "hour"]
        means = train.groupby(keys)[P1_TARGET].mean().rename("_mean")
        fallback = frame[keys].join(means, on=keys)["_mean"]
        prediction = prediction.fillna(fallback).fillna(float(train[P1_TARGET].mean()))
    return prediction.to_numpy()


def make_demand_model():
    """Candidato de P1: gradiente boosting con pérdida de Poisson para conteos."""
    return HistGradientBoostingRegressor(loss="poisson", random_state=cfg.SEED)


# ---------------------------------------------------------------------------
# P2: baseline logístico y modelo candidato
# ---------------------------------------------------------------------------
def make_risk_baseline():
    """Baseline de P2: regresión logística de tres clases con pesos balanceados."""
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000, class_weight="balanced", random_state=cfg.SEED),
    )


def make_risk_model():
    """Candidato de P2: gradiente boosting con pesos calculados en entrenamiento."""
    return HistGradientBoostingClassifier(class_weight="balanced", random_state=cfg.SEED)


def class_probabilities(model, features):
    """Probabilidades en el orden de ``P2_CLASSES``; falla si el modelo no vio las tres clases."""
    if list(model.classes_) != list(P2_CLASSES):
        raise ValueError(f"El entrenamiento no contiene las clases {P2_CLASSES}: {model.classes_}")
    return model.predict_proba(features)


# ---------------------------------------------------------------------------
# P3: agrupaciones
# ---------------------------------------------------------------------------
CLUSTERERS = {
    "kmeans": lambda: KMeans(
        n_clusters=cfg.N_CLUSTERS, n_init=cfg.KMEANS_N_INIT, random_state=cfg.SEED
    ),
    "ward": lambda: AgglomerativeClustering(n_clusters=cfg.N_CLUSTERS, linkage="ward"),
}


def cluster_metrics(train, val, algorithm):
    """Silhouette y Davies-Bouldin en entrenamiento; ARI entre entrenamiento y validación.

    El ARI compara las etiquetas del perfil de entrenamiento con las de una agrupación ajustada
    de forma independiente al perfil de validación, solo en estaciones comunes. Regresa
    ``(etiquetas_train, métricas)``.
    """
    columns = list(cfg.P3_FEATURE_COLUMNS)
    labels = CLUSTERERS[algorithm]().fit_predict(train[columns].to_numpy())
    metrics = {
        "train_silhouette": float(silhouette_score(train[columns], labels)),
        "train_davies_bouldin": float(davies_bouldin_score(train[columns], labels)),
        "train_stations": int(len(train)),
    }
    for group, size in zip(*np.unique(labels, return_counts=True)):
        metrics[f"train_size_cluster_{group}"] = int(size)
    val_labels = CLUSTERERS[algorithm]().fit_predict(val[columns].to_numpy())
    train_by_station = pd.Series(labels, index=train["station_id"].to_numpy())
    val_by_station = pd.Series(val_labels, index=val["station_id"].to_numpy())
    common = train_by_station.index.intersection(val_by_station.index)
    metrics["val_common_stations"] = int(len(common))
    if len(common) > cfg.N_CLUSTERS:
        metrics["val_ari"] = float(
            adjusted_rand_score(train_by_station.loc[common], val_by_station.loc[common])
        )
    return labels, metrics


# ---------------------------------------------------------------------------
# Figuras (agregadas por estación u hora; sin datos personales)
# ---------------------------------------------------------------------------
def _save(fig, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def plot_demand_by_hour(frame, prediction, title, path):
    """Demanda media observada y predicha por hora del día."""
    data = pd.DataFrame(
        {
            "hora": frame["hour"].to_numpy(),
            "observada": frame[P1_TARGET].to_numpy(),
            "predicha": np.asarray(prediction),
        }
    )
    fig, ax = plt.subplots(figsize=(7, 4))
    data.groupby("hora").mean().plot(ax=ax, marker="o")
    ax.set(title=title, xlabel="Hora del día", ylabel="Viajes por estación y hora")
    return _save(fig, path)


def plot_confusion(y_true, y_pred, title, path):
    """Matriz de confusión normalizada por clase real."""
    fig, ax = plt.subplots(figsize=(6, 5))
    ConfusionMatrixDisplay.from_predictions(
        y_true,
        y_pred,
        labels=list(P2_CLASSES),
        display_labels=list(cfg.P2_CLASS_NAMES),
        normalize="true",
        values_format=".2f",
        colorbar=False,
        ax=ax,
    )
    ax.set_title(title)
    ax.tick_params(axis="x", labelrotation=20)
    return _save(fig, path)


def plot_clusters(profiles, labels, title, path):
    """Mapa de estaciones por grupo y perfil horario medio (día laborable) de cada grupo."""
    fig, (ax_map, ax_profile) = plt.subplots(1, 2, figsize=(12, 5))
    scatter = ax_map.scatter(
        profiles["longitude"], profiles["latitude"], c=labels, cmap="tab10", s=18
    )
    ax_map.set(title="Ubicación de las estaciones", xlabel="Longitud", ylabel="Latitud")
    ax_map.legend(*scatter.legend_elements(), title="Grupo", fontsize=8)
    hours = range(cfg.PROFILE_HOURS)
    weekday = [f"weekday_{hour:02d}" for hour in hours]
    for group in np.unique(labels):
        ax_profile.plot(
            hours, profiles.loc[labels == group, weekday].mean(), label=f"Grupo {group}"
        )
    ax_profile.set(
        title="Perfil horario medio (día laborable)",
        xlabel="Hora del día",
        ylabel="Fracción de las salidas",
    )
    ax_profile.legend(fontsize=8)
    fig.suptitle(title)
    return _save(fig, path)


# ---------------------------------------------------------------------------
# Registro en MLflow
# ---------------------------------------------------------------------------
def _git(*args):
    try:
        result = subprocess.run(
            ["git", *args], cwd=cfg.ROOT_DIR, capture_output=True, text=True, timeout=15
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _manifest_value(path, key):
    try:
        return str(json.loads(Path(path).read_text(encoding="utf-8"))[key])
    except (OSError, KeyError, ValueError):
        return "no disponible"


def run_context():
    """Commit de Git y versiones de datos y variables que quedan ligados a cada run."""
    dirty = _git("status", "--porcelain", "--untracked-files=no")
    return {
        "git_commit": _git("rev-parse", "HEAD") or "desconocido",
        "git_dirty": "desconocido" if dirty is None else str(bool(dirty)).lower(),
        "data_version": _manifest_value(cfg.MANIFEST_PATH, "data_version"),
        "feature_version": _manifest_value(cfg.FEATURE_MANIFEST_PATH, "feature_version"),
    }


def configure_mlflow(
    tracking_uri=cfg.TRACKING_URI,
    experiment=cfg.EXPERIMENT_NAME,
    artifact_root=cfg.ROOT_DIR / "mlartifacts",
):
    """Apunta MLflow a la base local y crea el experimento con una carpeta de artefactos fija."""
    import mlflow

    mlflow.set_tracking_uri(tracking_uri)
    if mlflow.get_experiment_by_name(experiment) is None:
        mlflow.create_experiment(
            experiment, artifact_location=Path(artifact_root).resolve().as_uri()
        )
    mlflow.set_experiment(experiment)
    return mlflow


def _common_params(context, features, rows):
    return {
        "seed": cfg.SEED,
        "train_start": cfg.START_DATE.isoformat(),
        "train_end_exclusive": cfg.TRAIN_END.isoformat(),
        "validation_end_exclusive": cfg.VALIDATION_END.isoformat(),
        "test_end_exclusive": cfg.END_DATE_EXCLUSIVE.isoformat(),
        "horizon_hours": cfg.HORIZON_HOURS,
        "data_version": context["data_version"],
        "feature_version": context["feature_version"],
        "n_features": len(features),
        "features": ",".join(features),
        **{f"rows_{name}": int(count) for name, count in rows.items()},
    }


def log_run(run_name, question, kind, params, metrics, artifacts, context, undefined=()):
    """Crea un run con etiquetas, parámetros, métricas finitas y artefactos. Regresa su id."""
    import mlflow

    with mlflow.start_run(run_name=run_name) as run:
        mlflow.set_tags(
            {
                "equipo": cfg.TEAM,
                "pregunta": question,
                "tipo": kind,
                "git_commit": context["git_commit"],
                "git_dirty": context["git_dirty"],
                "metricas_no_definidas": ",".join(undefined) or "ninguna",
            }
        )
        mlflow.log_params({key: str(value) for key, value in params.items()})
        mlflow.log_metrics({k: v for k, v in metrics.items() if math.isfinite(v)})
        for artifact in artifacts:
            folder = "figuras" if Path(artifact).suffix == ".png" else "tablas"
            mlflow.log_artifact(str(artifact), artifact_path=folder)
        return run.info.run_id


def _print_results(question, results):
    table = pd.DataFrame(results).T
    print(f"\n=== {question}: resultados (run, métrica) ===", flush=True)
    print(table.round(4).to_string(), flush=True)


# ---------------------------------------------------------------------------
# Ejecución por pregunta
# ---------------------------------------------------------------------------
def _split_frames(data, final_test):
    frames = {name: data[data["split"] == name] for name in ("train", "val", "test")}
    if frames["train"].empty or frames["val"].empty:
        raise ValueError("Faltan filas de entrenamiento o validación en la tabla de variables")
    evaluated = {"val": frames["val"]}
    if final_test:
        evaluated["test"] = frames["test"]
    return frames, evaluated


def run_p1(tables=None, final_test=False, figures_dir=cfg.FIGURES_DIR, context=None):
    """P1: baseline estacional y gradiente boosting de Poisson. Regresa métricas por run."""
    data = tables if tables is not None else pd.read_parquet(cfg.FEATURE_FILES["p1"])
    context = context or run_context()
    features = list(cfg.P1_FEATURE_COLUMNS)
    frames, evaluated = _split_frames(data, final_test)
    train = frames["train"]
    rows = {name: len(frame) for name, frame in frames.items()}
    results = {}

    predictions = {name: weekly_baseline(train, frame) for name, frame in evaluated.items()}
    metrics = {}
    for name, frame in evaluated.items():
        metrics.update(regression_metrics(frame[P1_TARGET], predictions[name], name))
    figure = plot_demand_by_hour(
        evaluated["val"],
        predictions["val"],
        f"P1 baseline estacional: demanda por hora ({HORIZON_LABEL}, validación)",
        Path(figures_dir) / f"p1_estacional_{HORIZON_LABEL}.png",
    )
    run_name = f"P1_estacional_{HORIZON_LABEL}"
    params = {
        **_common_params(context, features, rows),
        "modelo": "misma estación y hora, semana anterior",
    }
    log_run(run_name, "P1", "baseline", params, metrics, [figure], context)
    results[run_name] = metrics

    model = make_demand_model().fit(train[features], train[P1_TARGET])
    predictions = {name: model.predict(frame[features]) for name, frame in evaluated.items()}
    metrics = {}
    for name, frame in evaluated.items():
        metrics.update(regression_metrics(frame[P1_TARGET], predictions[name], name))
    figure = plot_demand_by_hour(
        evaluated["val"],
        predictions["val"],
        f"P1 gradiente boosting: demanda por hora ({HORIZON_LABEL}, validación)",
        Path(figures_dir) / f"p1_hgb_poisson_{HORIZON_LABEL}.png",
    )
    run_name = f"P1_hgb_poisson_{HORIZON_LABEL}"
    params = {
        **_common_params(context, features, rows),
        "modelo": "HistGradientBoostingRegressor",
        "loss": "poisson",
        "learning_rate": model.learning_rate,
        "max_iter": model.max_iter,
        "max_leaf_nodes": model.max_leaf_nodes,
    }
    params.update(model.get_params())
    log_run(run_name, "P1", "candidato", params, metrics, [figure], context)
    results[run_name] = metrics
    _print_results("P1", results)
    return results


def run_p2(tables=None, final_test=False, figures_dir=cfg.FIGURES_DIR, context=None):
    """P2: regresión logística balanceada y gradiente boosting. Regresa métricas por run."""
    data = tables if tables is not None else pd.read_parquet(cfg.FEATURE_FILES["p2"])
    context = context or run_context()
    features = list(cfg.P2_FEATURE_COLUMNS)
    frames, evaluated = _split_frames(data, final_test)
    train = frames["train"]
    rows = {name: len(frame) for name, frame in frames.items()}
    class_counts = {
        f"train_clase_{cfg.P2_CLASS_NAMES[label]}": int((train[P2_TARGET] == label).sum())
        for label in P2_CLASSES
    }
    results = {}
    candidates = [
        ("logistica_proxy", "baseline", make_risk_baseline(), "LogisticRegression"),
        ("hgb_proxy", "candidato", make_risk_model(), "HistGradientBoostingClassifier"),
    ]
    for key, kind, model, description in candidates:
        model.fit(train[features], train[P2_TARGET])
        metrics, undefined, predicted = {}, [], {}
        for name, frame in evaluated.items():
            probabilities = class_probabilities(model, frame[features])
            predicted[name] = np.asarray(P2_CLASSES)[probabilities.argmax(axis=1)]
            values, missing = classification_metrics(
                frame[P2_TARGET], predicted[name], probabilities, name
            )
            metrics.update(values)
            undefined += missing
        run_name = f"P2_{key}_{HORIZON_LABEL}"
        figure = plot_confusion(
            evaluated["val"][P2_TARGET],
            predicted["val"],
            f"P2 {key}: matriz de confusión (validación)",
            Path(figures_dir) / f"p2_{key}_{HORIZON_LABEL}.png",
        )
        params = {
            **_common_params(context, features, rows),
            **class_counts,
            "modelo": description,
            "class_weight": "balanced",
            "initial_occupancy": cfg.INITIAL_OCCUPANCY,
            "low_occupancy": cfg.LOW_OCCUPANCY,
            "high_occupancy": cfg.HIGH_OCCUPANCY,
        }
        estimator = model.steps[-1][1] if hasattr(model, "steps") else model
        params.update(estimator.get_params())
        log_run(run_name, "P2", kind, params, metrics, [figure], context, undefined)
        results[run_name] = metrics
    _print_results("P2", results)
    return results


def run_p3(tables=None, figures_dir=cfg.FIGURES_DIR, output_dir=cfg.PROCESSED_DIR, context=None):
    """P3: K-means (baseline) y Ward (candidato) sobre 48 medias horarias normalizadas."""
    if tables is None:
        tables = {
            name: pd.read_parquet(cfg.FEATURE_FILES[f"p3_{name}"]) for name in ("train", "val")
        }
    train, val = tables["train"], tables["val"]
    context = context or run_context()
    features = list(cfg.P3_FEATURE_COLUMNS)
    rows = {"train": len(train), "val": len(val)}
    results = {}
    for key, kind, description in [
        ("kmeans", "baseline", "KMeans"),
        ("ward", "candidato", "AgglomerativeClustering(ward)"),
    ]:
        labels, metrics = cluster_metrics(train, val, key)
        run_name = f"P3_{key}_perfil48"
        figure = plot_clusters(
            train,
            labels,
            f"P3 {key}: {cfg.N_CLUSTERS} grupos por perfil horario (entrenamiento)",
            Path(figures_dir) / f"p3_{key}_perfil48.png",
        )
        assignments = Path(output_dir) / f"p3_grupos_{key}.csv"
        assignments.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            {
                "station_id": train["station_id"],
                "name": train["name"],
                "latitude": train["latitude"],
                "longitude": train["longitude"],
                "cluster": labels,
            }
        ).to_csv(assignments, index=False)
        params = {
            **_common_params(context, features, rows),
            "modelo": description,
            "n_clusters": cfg.N_CLUSTERS,
            "min_profile_days": cfg.MIN_PROFILE_DAYS,
            "coordenadas_en_agrupacion": "no (solo para el mapa)",
        }
        params.update(CLUSTERERS[key]().get_params())
        undefined = [] if "val_ari" in metrics else ["val_ari"]
        log_run(run_name, "P3", kind, params, metrics, [figure, assignments], context, undefined)
        results[run_name] = metrics
    _print_results("P3", results)
    return results


RUNNERS = {"P1": run_p1, "P2": run_p2, "P3": run_p3}


def main(argv=None):
    """Entrena y registra en MLflow las preguntas pedidas."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--question", choices=["P1", "P2", "P3", "all"], default="all")
    parser.add_argument(
        "--final-test",
        action="store_true",
        help="añade métricas test_ (septiembre); úsalo una sola vez, con decisiones ya fijas",
    )
    args = parser.parse_args(argv)
    configure_mlflow()
    context = run_context()
    print(f"Experimento: {cfg.EXPERIMENT_NAME} | commit: {context['git_commit'][:8]}", flush=True)
    if context["git_dirty"] == "true":
        print("Aviso: hay cambios sin commit; el commit registrado no describe el código exacto.")
    questions = list(RUNNERS) if args.question == "all" else [args.question]
    for question in questions:
        kwargs = {"context": context}
        if question != "P3":
            kwargs["final_test"] = args.final_test
        RUNNERS[question](**kwargs)
    print("\nListo. Para ver los runs: mlflow ui --backend-store-uri", cfg.TRACKING_URI)


if __name__ == "__main__":
    main()
