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
import itertools
import json
import math
import os
from pathlib import Path
import subprocess
import time
import warnings

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
    precision_recall_curve,
    r2_score,
    root_mean_squared_error,
    silhouette_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from mibici import config as cfg
from mibici.deployable import PersistenceRisk, SeasonalDemand, StationGroups
from mibici.stations import GROUP_COLUMN, MAX_CATEGORIES, StationGrouper
from mibici.tracking import (
    check_registered_model,
    log_bundle,
    log_model_check,
    project_run,
    verify_inputs,
)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

P1_TARGET = "target_departures"
P2_TARGET = "target_risk"
P2_CLASSES = (0, 1, 2)
# Variables de P1 más la estación como categórica. Se define aquí y no en config.py porque el hash
# de config.py forma parte de los manifiestos de datos; P1_FEATURE_COLUMNS queda intacta.
P1_FEATURE_COLUMNS_V2 = (*cfg.P1_FEATURE_COLUMNS, "station_id")
HORIZON_LABEL = f"h{cfg.HORIZON_HOURS}"

# Registro de modelos: un nombre por pregunta y el alias de la versión elegida.
REGISTERED_MODELS = {"P1": "mibici-p1-demanda", "P2": "mibici-p2-riesgo", "P3": "mibici-p3-grupos"}
CHAMPION_ALIAS = "champion"
# Regla de elección del campeón: solo métricas de validación. (métrica, True si mayor es mejor)
CHAMPION_RULE = {"P1": ("val_mae", False), "P2": ("val_f1_macro", True), "P3": ("val_ari", True)}
MODEL_ARTIFACT = "model"
# MLflow guarda con skops; HistGradientBoosting usa este tipo y hay que declararlo como confiable.
TRUSTED_TYPES = ["sklearn.ensemble._hist_gradient_boosting.predictor.TreePredictor"]
# Tipos adicionales que skops pide declarar para el modelo con estación categórica: la clase propia
# y dos piezas internas de scikit-learn (el preprocesador de categóricas del boosting).
STATION_MODEL_TRUSTED_TYPES = [
    "mibici.stations.StationGrouper",
    "functools.partial",
    "sklearn.utils.validation.check_array",
]
INPUT_EXAMPLE_ROWS = 5

# Búsqueda de hiperparámetros (opción --tune): cuadrícula pequeña evaluada solo en validación y
# sobre una muestra aleatoria reproducible del entrenamiento, para que no tarde horas. Los rangos
# viven aquí y no en config.py porque el hash de config.py forma parte de los manifiestos de datos.
SEARCH_SAMPLE_ROWS = 300_000
SEARCH_GRID = {
    "learning_rate": (0.05, 0.1),
    "max_leaf_nodes": (15, 31, 63),
    "max_iter": (100, 300),
}


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


def make_demand_model(**params):
    """Candidato de P1: gradiente boosting con pérdida de Poisson para conteos."""
    return HistGradientBoostingRegressor(
        loss="poisson", **{**cfg.HGB_DEFAULTS, "random_state": cfg.SEED, **params}
    )


def make_demand_station_model(**params):
    """Candidato de P1 con la estación como categórica (las menos frecuentes van a "otras").

    El agrupamiento de estaciones forma parte del modelo, así que se aprende solo con el
    entrenamiento y viaja con el modelo guardado: al predecir basta pasar ``station_id``.
    """
    return make_pipeline(
        StationGrouper(max_categories=MAX_CATEGORIES),
        HistGradientBoostingRegressor(
            loss="poisson",
            categorical_features=[GROUP_COLUMN],
            **{**cfg.HGB_DEFAULTS, "random_state": cfg.SEED, **params},
        ),
    )


# ---------------------------------------------------------------------------
# P2: baseline logístico y modelo candidato
# ---------------------------------------------------------------------------
def make_risk_baseline(**params):
    """Baseline de P2: regresión logística de tres clases con pesos balanceados."""
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(
            class_weight="balanced",
            **{**cfg.LOGISTIC_DEFAULTS, "random_state": cfg.SEED, **params},
        ),
    )


def make_risk_model(**params):
    """Candidato de P2: gradiente boosting con pesos calculados en entrenamiento."""
    return HistGradientBoostingClassifier(
        class_weight="balanced", **{**cfg.HGB_DEFAULTS, "random_state": cfg.SEED, **params}
    )


def persistence_classes(frame):
    """Regla sin aprendizaje: la clase de la próxima hora es la de la ocupación virtual actual.

    "Sin bicicletas" si ``virtual_occupancy <= LOW_OCCUPANCY``, "sin anclajes" si es
    ``>= HIGH_OCCUPANCY`` y "normal" en otro caso: los mismos umbrales con los que se define la
    etiqueta, aplicados a la ocupación de la hora actual en vez de la siguiente.
    """
    occupancy = frame["virtual_occupancy"].to_numpy(dtype=float)
    return np.select(
        [occupancy <= cfg.LOW_OCCUPANCY, occupancy >= cfg.HIGH_OCCUPANCY], [1, 2], default=0
    ).astype("int8")


def one_hot_probabilities(classes):
    """Probabilidades 0/1 en el orden de ``P2_CLASSES``, para calcular AP de una regla dura."""
    return (np.asarray(classes)[:, None] == np.asarray(P2_CLASSES)[None, :]).astype(float)


def class_probabilities(model, features):
    """Probabilidades en el orden de ``P2_CLASSES``; falla si el modelo no vio las tres clases."""
    if list(model.classes_) != list(P2_CLASSES):
        raise ValueError(f"El entrenamiento no contiene las clases {P2_CLASSES}: {model.classes_}")
    return model.predict_proba(features)


# ---------------------------------------------------------------------------
# P3: agrupaciones
# ---------------------------------------------------------------------------
CLUSTERERS = {
    "kmeans": lambda k=cfg.N_CLUSTERS: KMeans(
        n_clusters=k, n_init=cfg.KMEANS_N_INIT, random_state=cfg.SEED
    ),
    "ward": lambda k=cfg.N_CLUSTERS: AgglomerativeClustering(n_clusters=k, linkage="ward"),
}
# Barrido de k (justifica cuántos grupos usar). Vive aquí y no en config.py porque el hash de
# config.py forma parte de los manifiestos de datos.
P3_K_VALUES = tuple(range(2, 9))


def cluster_metrics(train, val, algorithm, k=cfg.N_CLUSTERS, model=None, seed=cfg.SEED):
    """Silhouette y Davies-Bouldin en entrenamiento; ARI entre entrenamiento y validación.

    El ARI compara las etiquetas del perfil de entrenamiento con las de una agrupación ajustada
    de forma independiente al perfil de validación, solo en estaciones comunes. Regresa
    ``(etiquetas_train, métricas)``.
    """
    columns = list(cfg.P3_FEATURE_COLUMNS)
    labels = (
        model.labels_
        if model is not None
        else CLUSTERERS[algorithm](k).fit_predict(train[columns].to_numpy())
    )
    metrics = {
        "train_silhouette": float(silhouette_score(train[columns], labels)),
        "train_davies_bouldin": float(davies_bouldin_score(train[columns], labels)),
        "train_stations": int(len(train)),
    }
    sizes = np.unique(labels, return_counts=True)
    for group, size in zip(*sizes):
        metrics[f"train_size_cluster_{group}"] = int(size)
    metrics["train_min_cluster_size"] = int(sizes[1].min())
    validation_model = CLUSTERERS[algorithm](k)
    if algorithm == "kmeans":
        validation_model.set_params(random_state=seed)
    val_labels = validation_model.fit_predict(val[columns].to_numpy())
    train_by_station = pd.Series(labels, index=train["station_id"].to_numpy())
    val_by_station = pd.Series(val_labels, index=val["station_id"].to_numpy())
    common = train_by_station.index.intersection(val_by_station.index)
    metrics["val_common_stations"] = int(len(common))
    if len(common) > k:
        metrics["val_ari"] = float(
            adjusted_rand_score(train_by_station.loc[common], val_by_station.loc[common])
        )
    if model is not None:
        predicted = model.predict(val[columns])
        if 1 < len(np.unique(predicted)) < len(predicted):
            metrics["val_assignment_silhouette"] = float(silhouette_score(val[columns], predicted))
            metrics["val_assignment_davies_bouldin"] = float(
                davies_bouldin_score(val[columns], predicted)
            )
        metrics["val_assignment_ari"] = float(adjusted_rand_score(val_labels, predicted))
    return labels, metrics


def k_sweep_table(train, val):
    """Métricas de K-means y Ward para cada k de ``P3_K_VALUES``, solo con entrenamiento y validación."""
    rows = []
    for algorithm in CLUSTERERS:
        for k in P3_K_VALUES:
            _, metrics = cluster_metrics(train, val, algorithm, k)
            rows.append(
                {
                    "algoritmo": algorithm,
                    "k": k,
                    **{
                        name: metrics.get(name, math.nan)
                        for name in (
                            "train_silhouette",
                            "train_davies_bouldin",
                            "val_ari",
                            "train_min_cluster_size",
                        )
                    },
                }
            )
    return pd.DataFrame(rows)


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


def plot_precision_recall(y_true, probabilities, path):
    fig, ax = plt.subplots(figsize=(7, 4))
    for label, name in enumerate(cfg.P2_CLASS_NAMES):
        binary = np.asarray(y_true) == label
        if binary.any() and not binary.all():
            precision, recall, _ = precision_recall_curve(binary, probabilities[:, label])
            ax.plot(recall, precision, label=name)
    ax.set(xlabel="Recall", ylabel="Precisión", title="P2: precisión-recall en validación")
    ax.legend(fontsize=8)
    return _save(fig, path)


def inference_cost(model, features):
    sample = features.head(min(1000, len(features)))
    start = time.perf_counter()
    model.predict(sample)
    return (time.perf_counter() - start) * 1000 / len(sample)


def plot_k_sweep(table, title, path):
    """Silhouette, Davies-Bouldin y ARI contra k, una línea por algoritmo."""
    panels = [
        ("train_silhouette", "Silhouette (mayor es mejor)"),
        ("train_davies_bouldin", "Davies-Bouldin (menor es mejor)"),
        ("val_ari", "ARI entrenamiento vs validación (mayor es mejor)"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    for ax, (metric, label) in zip(axes, panels):
        for algorithm, group in table.groupby("algoritmo"):
            ax.plot(group["k"], group[metric], marker="o", label=algorithm)
        ax.set(title=label, xlabel="Número de grupos k")
        ax.set_xticks(list(P3_K_VALUES))
        ax.legend(fontsize=8)
    fig.suptitle(title)
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
    tracking_uri=None,
    experiment=cfg.EXPERIMENT_NAME,
    artifact_root=cfg.ROOT_DIR / "mlartifacts",
):
    """Apunta MLflow a la base local y crea el experimento con una carpeta de artefactos fija."""
    import mlflow

    tracking_uri = tracking_uri or os.environ.get("MLFLOW_TRACKING_URI") or cfg.TRACKING_URI
    mlflow.set_tracking_uri(tracking_uri)
    if mlflow.get_experiment_by_name(experiment) is None:
        if tracking_uri.startswith(("http://", "https://")):
            mlflow.create_experiment(experiment)
        else:
            mlflow.create_experiment(
                experiment, artifact_location=Path(artifact_root).resolve().as_uri()
            )
    mlflow.set_experiment(experiment)
    return mlflow


def _common_params(context, features, rows, seed=cfg.SEED):
    return {
        "seed": seed,
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


def run_tags(question, kind, context, undefined=()):
    """Etiquetas comunes de todos los runs."""
    return {
        "equipo": cfg.TEAM,
        "pregunta": question,
        "tipo": kind,
        "question": question.lower(),
        "stage_of_work": {"baseline": "baseline", "candidato": "candidate"}.get(kind, "search"),
        "git_commit": context["git_commit"],
        "git_dirty": context["git_dirty"],
        "data_version": context["data_version"],
        "feature_version": context["feature_version"],
        "metricas_no_definidas": ",".join(undefined) or "ninguna",
    }


def log_run(
    run_name,
    question,
    kind,
    params,
    metrics,
    artifacts,
    context,
    undefined=(),
    model=None,
    input_example=None,
    nested=False,
    training=None,
    target=None,
):
    """Crea un run con etiquetas, parámetros, métricas finitas y artefactos. Regresa su id.

    Si se pasa ``model`` (estimador de scikit-learn ya entrenado) se guarda con su firma, que
    registra columnas y tipos de entrada y el tipo de salida. ``input_example`` son unas filas de
    entrenamiento con las columnas predictoras; de ahí se infiere la firma.
    """
    import mlflow

    with mlflow.start_run(
        run_name=run_name, nested=nested or mlflow.active_run() is not None
    ) as run:
        mlflow.set_tags(run_tags(question, kind, context, undefined))
        mlflow.set_tag("model_family", params.get("modelo", type(model).__name__))
        mlflow.log_params({key: str(value) for key, value in params.items()})
        mlflow.log_metrics({k: v for k, v in metrics.items() if math.isfinite(v)})
        log_bundle(context, params, training, target)
        for artifact in artifacts:
            folder = "figuras" if Path(artifact).suffix == ".png" else "tablas"
            mlflow.log_artifact(str(artifact), artifact_path=folder)
        if model is not None:
            log_model(model, input_example)
        return run.info.run_id


def trusted_types(model):
    """Tipos que skops debe aceptar al guardar y cargar este modelo."""
    steps = getattr(model, "steps", [])
    if steps and isinstance(steps[0][1], StationGrouper):
        return [*TRUSTED_TYPES, *STATION_MODEL_TRUSTED_TYPES]
    if isinstance(model, (PersistenceRisk, SeasonalDemand, StationGroups)):
        return [*TRUSTED_TYPES, f"mibici.deployable.{type(model).__name__}"]
    return list(TRUSTED_TYPES)


def log_model(model, input_example):
    """Guarda el modelo en el run activo con firma y ejemplo de entrada."""
    import mlflow
    from mlflow.models import infer_signature

    if input_example is None or len(input_example) == 0:
        raise ValueError("Guardar un modelo requiere filas de ejemplo para inferir la firma")
    example = input_example.head(INPUT_EXAMPLE_ROWS)
    with warnings.catch_warnings():
        # Aviso informativo sobre enteros y valores faltantes; las variables enteras no los tienen.
        warnings.filterwarnings("ignore", message="Hint: Inferred schema contains integer")
        signature = infer_signature(example, model.predict(example))
        info = mlflow.sklearn.log_model(
            model,
            name=MODEL_ARTIFACT,
            signature=signature,
            input_example=example,
            skops_trusted_types=trusted_types(model),
            code_paths=[str(cfg.ROOT_DIR / "mibici")],
            pip_requirements=[
                line
                for line in (cfg.ROOT_DIR / "requirements.txt").read_text().splitlines()
                if line and not line.startswith("-e")
            ],
        )
    log_model_check(model, example)
    return info


def model_uri(run_id):
    """URI ``models:/<id>`` del modelo que guardó el run; MLflow 3 no lo deja bajo el run."""
    import mlflow

    outputs = mlflow.tracking.MlflowClient().get_run(run_id).outputs.model_outputs
    if not outputs:
        raise ValueError(f"El run {run_id} no guardó ningún modelo")
    return f"models:/{outputs[-1].model_id}"


def pick_champion(question, candidates):
    """Elige el modelo ganador usando solo la métrica de validación definida en CHAMPION_RULE.

    ``candidates`` es ``{run_name: (run_id, metrics, tiene_modelo)}``. Solo compiten los runs que
    guardaron un estimador, porque el registro necesita algo que se pueda cargar y usar. Una
    métrica ausente o no finita descalifica al run. Regresa ``None`` si ninguno califica.
    """
    metric, higher_is_better = CHAMPION_RULE[question]
    valid = {
        name: item
        for name, item in candidates.items()
        if item[2] and metric in item[1] and math.isfinite(item[1][metric])
    }
    if not valid:
        return None
    sign = 1 if higher_is_better else -1

    def score(name):
        values = valid[name][1]
        return (
            sign * values[metric],
            values.get("train_silhouette", 0.0),
            -values.get("train_davies_bouldin", 0.0),
            -values.get("inference_seconds_per_1000", 0.0),
        )

    return max(valid, key=score)


def baselines_beating(question, best, candidates):
    """Nombres de los runs sin modelo (baselines) que superan al ganador en la métrica de elección."""
    metric, higher_is_better = CHAMPION_RULE[question]
    sign = 1 if higher_is_better else -1
    reference = candidates[best][1][metric]
    return [
        name
        for name, (_, metrics, has_model) in candidates.items()
        if not has_model
        and math.isfinite(metrics.get(metric, math.nan))
        and sign * metrics[metric] > sign * reference
    ]


def register_champion(question, candidates):
    """Registra el modelo ganador en el Model Registry y le asigna el alias ``champion``.

    Cada ejecución crea una versión nueva del modelo registrado; el alias se mueve a la versión
    del ganador actual. Si una regla sin aprendizaje (baseline) lo supera en validación, el modelo
    se registra igual, pero la versión queda etiquetada ``supera_baselines=no`` y se avisa.
    Regresa ``(nombre_del_run, version)`` o ``None`` si no hay modelo.
    """
    import mlflow
    from mlflow.tracking import MlflowClient

    best = pick_champion(question, candidates)
    if best is None:
        print(f"{question}: ningún run guardó un modelo; no se registra nada.")
        return None
    run_id = candidates[best][0]
    name = REGISTERED_MODELS[question]
    version = mlflow.register_model(model_uri(run_id), name)
    client = MlflowClient()
    source = client.get_run(run_id)
    description = (
        f"Equipo {cfg.TEAM}, {question}. Selección por {CHAMPION_RULE[question][0]} en validación; "
        "la prueba no participa. P2 es un proxy simulado; P3 asigna perfiles por centroides "
        "(K-means) o por perfil de entrenamiento más cercano (Ward)."
    )
    client.update_registered_model(name, description=description)
    client.update_model_version(name, version.version, description=f"{description} Run: {run_id}.")
    for key, value in {
        "equipo": cfg.TEAM,
        "question": question.lower(),
        "git_commit": source.data.tags.get("git_commit", "desconocido"),
        "data_version": source.data.params.get("data_version", "desconocido"),
        "feature_version": source.data.params.get("feature_version", "desconocido"),
        "experiment_id": source.info.experiment_id,
    }.items():
        client.set_model_version_tag(name, version.version, key, value)
    candidate_alias = f"validated-{version.version}"
    client.set_registered_model_alias(name, candidate_alias, version.version)
    try:
        check_registered_model(name, candidate_alias)
    finally:
        client.delete_registered_model_alias(name, candidate_alias)
    client.set_model_version_tag(name, version.version, "validation_status", "passed")
    client.set_registered_model_alias(name, CHAMPION_ALIAS, version.version)
    metric = CHAMPION_RULE[question][0]
    beaten_by = baselines_beating(question, best, candidates)
    client.set_model_version_tag(name, version.version, "run_name", best)
    client.set_model_version_tag(name, version.version, "criterio", f"{metric} en validación")
    client.set_model_version_tag(
        name,
        version.version,
        "supera_baselines",
        "no: " + ", ".join(beaten_by) if beaten_by else "si",
    )
    print(f"{question}: {name} v{version.version} @{CHAMPION_ALIAS} <- {best}", flush=True)
    if beaten_by:
        print(
            f"Aviso {question}: {', '.join(beaten_by)} supera al modelo en {metric}; "
            "el modelo no aporta frente a esa regla.",
            flush=True,
        )
    return best, int(version.version)


def search_combinations():
    """Combinaciones de ``SEARCH_GRID`` como lista de diccionarios, en orden estable."""
    names = list(SEARCH_GRID)
    return [dict(zip(names, values)) for values in itertools.product(*SEARCH_GRID.values())]


def _combo_label(combo):
    return ", ".join(f"{key}={value}" for key, value in combo.items())


def plot_search(table, metric, higher_is_better, title, path):
    """Métrica de validación por combinación, con la ganadora resaltada."""
    ordered = table.sort_values(metric, ascending=not higher_is_better).reset_index(drop=True)
    colors = ["#1f77b4" if index == 0 else "#9aa5b1" for index in ordered.index]
    fig, ax = plt.subplots(figsize=(8, 0.4 * len(ordered) + 1.5))
    ax.barh(ordered["combinacion"][::-1], ordered[metric][::-1], color=colors[::-1])
    ax.set_xlabel(metric)
    ax.set_title(title)
    low, high = ordered[metric].min(), ordered[metric].max()
    margin = max((high - low) * 0.5, 1e-3)
    ax.set_xlim(low - margin, high + margin)
    return _save(fig, path)


def run_search(
    question, train, validation, features, figures_dir, context, seed=cfg.SEED, model_params=None
):
    """Búsqueda en cuadrícula con un run padre y un run hijo por combinación.

    Cada hijo entrena en una muestra de entrenamiento y mide únicamente en validación completa:
    nunca calcula métricas ``test_``. Regresa el diccionario de la mejor combinación según la
    métrica de ``CHAMPION_RULE``, la tabla de resultados y el id del run padre.
    """
    import mlflow

    metric, higher_is_better = CHAMPION_RULE[question]
    target = P1_TARGET if question == "P1" else P2_TARGET
    make = make_demand_model if question == "P1" else make_risk_model
    sample = train.sample(n=min(SEARCH_SAMPLE_ROWS, len(train)), random_state=seed)
    parent_name = f"{question}_busqueda_hgb_{HORIZON_LABEL}"
    rows = []
    with mlflow.start_run(run_name=parent_name, nested=mlflow.active_run() is not None) as parent:
        mlflow.set_tags(run_tags(question, "busqueda", context))
        mlflow.set_tag("model_family", "HistGradientBoosting")
        mlflow.log_params(
            {
                "modelo": "HistGradientBoosting",
                "criterio": f"{metric} en validación",
                "cuadricula": json.dumps({k: list(v) for k, v in SEARCH_GRID.items()}),
                "combinaciones": len(search_combinations()),
                "filas_muestra_entrenamiento": len(sample),
                "filas_entrenamiento": len(train),
                "filas_validacion": len(validation),
                "seed": seed,
            }
        )
        for index, combo in enumerate(search_combinations(), start=1):
            start = time.perf_counter()
            model = make(**{**(model_params or {}), **combo, "random_state": seed}).fit(
                sample[features], sample[target]
            )
            fit_seconds = time.perf_counter() - start
            if question == "P1":
                values = regression_metrics(
                    validation[target], model.predict(validation[features]), "val"
                )
                undefined = []
            else:
                probabilities = class_probabilities(model, validation[features])
                predicted = np.asarray(P2_CLASSES)[probabilities.argmax(axis=1)]
                values, undefined = classification_metrics(
                    validation[target], predicted, probabilities, "val"
                )
            values["fit_seconds"] = fit_seconds
            values["inference_seconds_per_1000"] = inference_cost(model, validation[features])
            folder = Path(figures_dir) / f"{question.lower()}_search_c{index:02d}"
            if question == "P1":
                figure = plot_demand_by_hour(
                    validation,
                    model.predict(validation[features]),
                    "P1: búsqueda, validación",
                    folder / "demand.png",
                )
                artifacts = [figure]
            else:
                artifacts = [
                    plot_confusion(
                        validation[target],
                        predicted,
                        "P2: búsqueda, validación",
                        folder / "confusion.png",
                    ),
                    plot_precision_recall(
                        validation[target], probabilities, folder / "precision_recall.png"
                    ),
                ]
            log_run(
                f"{parent_name}_c{index:02d}",
                question,
                "busqueda_hijo",
                {
                    **_common_params(
                        context, features, {"train": len(sample), "val": len(validation)}, seed
                    ),
                    "modelo": "HistGradientBoosting",
                    "combinacion": index,
                    "training_scope": "sample",
                    **model.get_params(),
                },
                values,
                artifacts,
                context,
                undefined,
                nested=True,
                model=model,
                input_example=sample[features],
                training=sample[[*features, target]],
                target=target,
            )
            rows.append({"combinacion": _combo_label(combo), **combo, **values})
        table = pd.DataFrame(rows)
        best_index = int(table[metric].idxmax() if higher_is_better else table[metric].idxmin())
        best = {key: table.loc[best_index, key] for key in SEARCH_GRID}
        best = {key: type(SEARCH_GRID[key][0])(value) for key, value in best.items()}
        mlflow.log_params({f"mejor_{key}": value for key, value in best.items()})
        mlflow.log_metric(f"mejor_{metric}", float(table.loc[best_index, metric]))
        Path(figures_dir).mkdir(parents=True, exist_ok=True)
        csv = Path(figures_dir) / f"{question.lower()}_busqueda_hgb_{HORIZON_LABEL}.csv"
        table.to_csv(csv, index=False)
        figure = plot_search(
            table,
            metric,
            higher_is_better,
            f"{question}: {metric} por combinación (validación, muestra de entrenamiento)",
            Path(figures_dir) / f"{question.lower()}_busqueda_hgb_{HORIZON_LABEL}.png",
        )
        mlflow.log_artifact(str(figure), artifact_path="figuras")
        mlflow.log_artifact(str(csv), artifact_path="tablas")
        return best, table, parent.info.run_id


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


def run_p1(
    tables=None,
    final_test=False,
    figures_dir=cfg.FIGURES_DIR,
    context=None,
    register=True,
    tune=False,
    model_name="all",
    model_params=None,
    seed=cfg.SEED,
):
    """P1: baseline estacional y gradiente boosting de Poisson. Regresa métricas por run."""
    data = tables if tables is not None else pd.read_parquet(cfg.FEATURE_FILES["p1"])
    context = context or run_context()
    features = list(cfg.P1_FEATURE_COLUMNS)
    model_params = {**(model_params or {}), "random_state": seed}
    frames, evaluated = _split_frames(data, final_test)
    train = frames["train"]
    rows = {name: len(frame) for name, frame in frames.items()}
    results = {}

    baseline_features = ["station_id", *features]
    baseline = SeasonalDemand().fit(train[baseline_features], train[P1_TARGET])
    predictions = {
        name: baseline.predict(frame[baseline_features]) for name, frame in evaluated.items()
    }
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
        **_common_params(context, baseline_features, rows, seed),
        "modelo": "misma estación y hora, semana anterior",
    }
    metrics["inference_seconds_per_1000"] = inference_cost(
        baseline, evaluated["val"][baseline_features]
    )
    run_id = log_run(
        run_name,
        "P1",
        "baseline",
        params,
        metrics,
        [figure],
        context,
        model=baseline,
        input_example=train[baseline_features],
        training=train[[*baseline_features, P1_TARGET]],
        target=P1_TARGET,
    )
    results[run_name] = metrics
    candidates = {run_name: (run_id, metrics, True)}

    variants = [
        (
            "hgb_poisson",
            lambda: make_demand_model(**model_params),
            {},
            features,
            "HistGradientBoostingRegressor",
        )
    ]
    variants.append(
        (
            "hgb_poisson_estacion",
            lambda: make_demand_station_model(**model_params),
            {},
            list(P1_FEATURE_COLUMNS_V2),
            "StationGrouper + HistGradientBoostingRegressor",
        )
    )
    if tune:
        best, _, search_id = run_search(
            "P1", train, evaluated["val"], features, figures_dir, context, seed, model_params
        )
        variants.append(
            (
                "hgb_poisson_ajustado",
                lambda: make_demand_model(**{**model_params, **best}),
                {"busqueda_run_id": search_id, **{f"mejor_{k}": v for k, v in best.items()}},
                features,
                "HistGradientBoostingRegressor",
            )
        )
    if model_name != "all":
        selected = {"seasonal": None, "hgb": "hgb_poisson", "hgb_station": "hgb_poisson_estacion"}
        variants = [variant for variant in variants if variant[0] == selected[model_name]]
    for key, factory, extra, columns, description in variants:
        start = time.perf_counter()
        model = factory().fit(train[columns], train[P1_TARGET])
        fit_seconds = time.perf_counter() - start
        predictions = {name: model.predict(frame[columns]) for name, frame in evaluated.items()}
        metrics = {}
        for name, frame in evaluated.items():
            metrics.update(regression_metrics(frame[P1_TARGET], predictions[name], name))
        metrics["fit_seconds"] = fit_seconds
        metrics["inference_seconds_per_1000"] = inference_cost(model, evaluated["val"][columns])
        figure = plot_demand_by_hour(
            evaluated["val"],
            predictions["val"],
            f"P1 {key}: demanda por hora ({HORIZON_LABEL}, validación)",
            Path(figures_dir) / f"p1_{key}_{HORIZON_LABEL}.png",
        )
        run_name = f"P1_{key}_{HORIZON_LABEL}"
        params = {
            **_common_params(context, columns, rows, seed),
            "modelo": description,
            "loss": "poisson",
            **extra,
        }
        estimator = model.steps[-1][1] if hasattr(model, "steps") else model
        params.update(estimator.get_params())
        if hasattr(model, "steps"):
            grouper = model.steps[0][1]
            params.update(
                {
                    "station_id": "categórica: estaciones frecuentes y 'otras'",
                    "categorias_estacion": grouper.n_categories_,
                    "estaciones_en_otras": grouper.n_grouped_stations_,
                }
            )
        run_id = log_run(
            run_name,
            "P1",
            "candidato",
            params,
            metrics,
            [figure],
            context,
            model=model,
            input_example=train[columns],
            training=train[[*columns, P1_TARGET]],
            target=P1_TARGET,
        )
        results[run_name] = metrics
        candidates[run_name] = (run_id, metrics, True)
    _print_results("P1", results)
    if register:
        register_champion("P1", candidates)
    return results


def run_p2(
    tables=None,
    final_test=False,
    figures_dir=cfg.FIGURES_DIR,
    context=None,
    register=True,
    tune=False,
    initial_occupancy=cfg.INITIAL_OCCUPANCY,
    suffix="",
    model_name="all",
    model_params=None,
    seed=cfg.SEED,
):
    """P2: regla de persistencia, regresión logística balanceada y boosting. Regresa métricas.

    ``initial_occupancy`` es la ocupación inicial con la que se construyó la tabla ``tables``; solo
    se registra como parámetro. ``suffix`` se agrega a los nombres de run y de figura (por ejemplo
    ``_occ25``) para distinguir los escenarios de sensibilidad.
    """
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
    registry_candidates = {}
    model_params = model_params or {}
    logistic_params = model_params if model_name == "logistic" else {}
    boosting_params = model_params if model_name in ("all", "hgb") else {}
    candidates = [
        (
            "persistencia_proxy",
            "baseline",
            PersistenceRisk(),
            "regla: clase de la ocupación virtual actual",
        ),
        (
            "logistica_proxy",
            "baseline",
            make_risk_baseline(**{**logistic_params, "random_state": seed}),
            "LogisticRegression",
        ),
        (
            "hgb_proxy",
            "candidato",
            make_risk_model(**{**boosting_params, "random_state": seed}),
            "HistGradientBoostingClassifier",
        ),
    ]
    extras = {}
    if tune:
        best, _, search_id = run_search(
            "P2", train, evaluated["val"], features, figures_dir, context, seed, boosting_params
        )
        candidates.append(
            (
                "hgb_ajustado_proxy",
                "candidato",
                make_risk_model(**{**boosting_params, **best, "random_state": seed}),
                "HistGradientBoostingClassifier (hiperparámetros ajustados)",
            )
        )
        extras["hgb_ajustado_proxy"] = {
            "busqueda_run_id": search_id,
            **{f"mejor_{k}": v for k, v in best.items()},
        }
    if model_name != "all":
        selected = {
            "persistence": "persistencia_proxy",
            "logistic": "logistica_proxy",
            "hgb": "hgb_proxy",
        }
        candidates = [
            item for item in candidates if item[0] in ("persistencia_proxy", selected[model_name])
        ]
    for key, kind, model, description in candidates:
        start = time.perf_counter()
        if model is not None:
            model.fit(train[features], train[P2_TARGET])
        fit_seconds = time.perf_counter() - start
        metrics, undefined, predicted = {}, [], {}
        for name, frame in evaluated.items():
            if model is None:
                predicted[name] = persistence_classes(frame)
                probabilities = one_hot_probabilities(predicted[name])
            else:
                probabilities = class_probabilities(model, frame[features])
                predicted[name] = np.asarray(P2_CLASSES)[probabilities.argmax(axis=1)]
            values, missing = classification_metrics(
                frame[P2_TARGET], predicted[name], probabilities, name
            )
            metrics.update(values)
            undefined += missing
        metrics["fit_seconds"] = fit_seconds
        metrics["inference_seconds_per_1000"] = inference_cost(model, evaluated["val"][features])
        run_name = f"P2_{key}_{HORIZON_LABEL}{suffix}"
        figure = plot_confusion(
            evaluated["val"][P2_TARGET],
            predicted["val"],
            f"P2 {key}{suffix}: matriz de confusión (validación)",
            Path(figures_dir) / f"p2_{key}_{HORIZON_LABEL}{suffix}.png",
        )
        probabilities_val = class_probabilities(model, evaluated["val"][features])
        pr_figure = plot_precision_recall(
            evaluated["val"][P2_TARGET],
            probabilities_val,
            Path(figures_dir) / f"p2_{key}_{HORIZON_LABEL}{suffix}_pr.png",
        )
        params = {
            **_common_params(context, features, rows, seed),
            **class_counts,
            "modelo": description,
            "initial_occupancy": initial_occupancy,
            "low_occupancy": cfg.LOW_OCCUPANCY,
            "high_occupancy": cfg.HIGH_OCCUPANCY,
            **extras.get(key, {}),
        }
        if model is not None:
            estimator = model.steps[-1][1] if hasattr(model, "steps") else model
            params.update(estimator.get_params())
        run_id = log_run(
            run_name,
            "P2",
            kind,
            params,
            metrics,
            [figure, pr_figure],
            context,
            undefined,
            model=model,
            input_example=train[features] if model is not None else None,
            training=train[[*features, P2_TARGET]],
            target=P2_TARGET,
        )
        results[run_name] = metrics
        registry_candidates[run_name] = (run_id, metrics, model is not None)
    _print_results("P2", results)
    if register:
        register_champion("P2", registry_candidates)
    return results


def log_cluster_candidate(
    train, val, algorithm, k, run_name, kind, figures_dir, output_dir, context, seed=cfg.SEED
):
    features = list(cfg.P3_FEATURE_COLUMNS)
    start = time.perf_counter()
    model = StationGroups(algorithm=algorithm, n_clusters=k, random_state=seed).fit(
        train[features]
    )
    fit_seconds = time.perf_counter() - start
    labels, metrics = cluster_metrics(train, val, algorithm, k, model=model, seed=seed)
    metrics["fit_seconds"] = fit_seconds
    metrics["inference_seconds_per_1000"] = inference_cost(model, val[features])
    figure = plot_clusters(
        train,
        labels,
        f"P3 {algorithm}: {k} grupos (entrenamiento)",
        Path(figures_dir) / f"{run_name.lower()}.png",
    )
    assignments = Path(output_dir) / f"{run_name.lower()}.csv"
    assignments.parent.mkdir(parents=True, exist_ok=True)
    train[["station_id", "name", "latitude", "longitude"]].assign(cluster=labels).to_csv(
        assignments, index=False
    )
    params = {
        **_common_params(context, features, {"train": len(train), "val": len(val)}, seed),
        **model.get_params(),
        "modelo": algorithm,
        "assignment_rule": model.assignment_rule_,
        "min_profile_days": cfg.MIN_PROFILE_DAYS,
        "coordenadas_en_agrupacion": "no (solo para el mapa)",
        "val_ari_definition": "independent_refit_between_periods",
    }
    run_id = log_run(
        run_name,
        "P3",
        kind,
        params,
        metrics,
        [figure, assignments],
        context,
        model=model,
        input_example=train[features],
        training=train[features],
    )
    return run_id, metrics


def run_k_sweep(train, val, figures_dir, context, output_dir=None, seed=cfg.SEED):
    import mlflow

    figures_dir = Path(figures_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)
    output_dir = Path(output_dir) if output_dir is not None else figures_dir / "assignments"
    candidates, rows = {}, []
    with mlflow.start_run(
        run_name="P3_barrido_k_perfil48", nested=mlflow.active_run() is not None
    ):
        mlflow.set_tags(run_tags("P3", "barrido", context))
        mlflow.set_tag("model_family", "clustering")
        params = {
            **_common_params(
                context, cfg.P3_FEATURE_COLUMNS, {"train": len(train), "val": len(val)}, seed
            ),
            "k_valores": ",".join(str(k) for k in P3_K_VALUES),
            "algoritmos": ",".join(CLUSTERERS),
            "k_fijado_antes": cfg.N_CLUSTERS,
        }
        mlflow.log_params(params)
        log_bundle(context, params)
        for algorithm in CLUSTERERS:
            for k in P3_K_VALUES:
                name = f"P3_{algorithm}_k{k}_perfil48"
                kind = "baseline" if algorithm == "kmeans" and k == cfg.N_CLUSTERS else "candidato"
                run_id, metrics = log_cluster_candidate(
                    train, val, algorithm, k, name, kind, figures_dir, output_dir, context, seed
                )
                candidates[name] = (run_id, metrics, True)
                rows.append({"algoritmo": algorithm, "k": k, **metrics})
                for metric in ("train_silhouette", "train_davies_bouldin", "val_ari"):
                    if math.isfinite(metrics.get(metric, math.nan)):
                        mlflow.log_metric(f"{algorithm}_{metric}", metrics[metric], step=k)
        table = pd.DataFrame(rows)
        csv = figures_dir / "p3_barrido_k_perfil48.csv"
        table.to_csv(csv, index=False)
        figure = plot_k_sweep(
            table,
            "P3: métricas por número de grupos (perfil de 48 valores)",
            figures_dir / "p3_barrido_k_perfil48.png",
        )
        mlflow.log_artifact(str(figure), artifact_path="figuras")
        mlflow.log_artifact(str(csv), artifact_path="tablas")
    table.attrs["registry_candidates"] = candidates
    return table


def run_p3(
    tables=None,
    figures_dir=cfg.FIGURES_DIR,
    output_dir=cfg.PROCESSED_DIR,
    context=None,
    register=True,
    model_name="all",
    n_clusters=cfg.N_CLUSTERS,
    seed=cfg.SEED,
):
    if tables is None:
        tables = {
            name: pd.read_parquet(cfg.FEATURE_FILES[f"p3_{name}"]) for name in ("train", "val")
        }
    train, val = tables["train"], tables["val"]
    context = context or run_context()
    results, candidates = {}, {}
    algorithms = [("kmeans", "baseline"), ("ward", "candidato")]
    if model_name != "all":
        algorithms = [item for item in algorithms if item[0] == model_name]
    for key, kind in algorithms:
        if n_clusters != cfg.N_CLUSTERS:
            kind = "candidato"
        name = (
            f"P3_{key}_perfil48"
            if n_clusters == cfg.N_CLUSTERS
            else f"P3_{key}_k{n_clusters}_perfil48"
        )
        run_id, metrics = log_cluster_candidate(
            train, val, key, n_clusters, name, kind, figures_dir, output_dir, context, seed
        )
        results[name] = metrics
        candidates[name] = (run_id, metrics, True)
    if model_name == "all":
        sweep = run_k_sweep(train, val, figures_dir, context, output_dir, seed)
        candidates.update(sweep.attrs["registry_candidates"])
    if register:
        register_champion("P3", candidates)
    _print_results("P3", results)
    return results


RUNNERS = {"P1": run_p1, "P2": run_p2, "P3": run_p3}


def main(argv=None):
    """Entrena y registra en MLflow las preguntas pedidas."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--question",
        type=lambda value: value.upper() if value.lower() != "all" else "all",
        choices=["P1", "P2", "P3", "all"],
        default="all",
    )
    parser.add_argument(
        "--model",
        default="all",
        help="all, seasonal, persistence, logistic, hgb, hgb_station, kmeans o ward",
    )
    parser.add_argument("--seed", type=int, default=cfg.SEED, help="Semilla reproducible")
    parser.add_argument("--learning-rate", type=float, help="Tasa de aprendizaje de HGB")
    parser.add_argument("--max-iter", type=int, help="Iteraciones de HGB o regresión logística")
    parser.add_argument("--max-leaf-nodes", type=int, help="Hojas por árbol de HGB")
    parser.add_argument("--l2-regularization", type=float, help="Regularización L2 de HGB")
    parser.add_argument("--c", type=float, help="Inverso de regularización logística")
    parser.add_argument("--n-clusters", type=int, default=cfg.N_CLUSTERS, help="Grupos para P3")
    parser.add_argument(
        "--final-test",
        action="store_true",
        help="añade métricas test_ (septiembre); úsalo una sola vez, con decisiones ya fijas",
    )
    parser.add_argument(
        "--tune",
        action="store_true",
        help="P1 y P2: busca hiperparámetros del boosting (run padre con hijos) y añade un run ajustado",
    )
    parser.add_argument(
        "--no-register",
        action="store_true",
        help="entrena y registra runs, pero no crea versiones ni alias en el Model Registry",
    )
    parser.add_argument(
        "--figures-dir",
        type=Path,
        default=cfg.FIGURES_DIR,
        help="Carpeta para figuras y tablas de esta ejecución",
    )
    args = parser.parse_args(argv)
    model_params = {
        key: getattr(args, key)
        for key in ("learning_rate", "max_iter", "max_leaf_nodes", "l2_regularization", "c")
        if getattr(args, key) is not None
    }
    allowed = {
        "P1": {"all", "seasonal", "hgb", "hgb_station"},
        "P2": {"all", "persistence", "logistic", "hgb"},
        "P3": {"all", "kmeans", "ward"},
        "all": {"all"},
    }
    if args.model not in allowed[args.question]:
        parser.error(f"Modelo {args.model} incompatible con {args.question}")
    if args.tune and args.model != "all":
        parser.error(
            "La búsqueda usa model=all; un modelo concreto recibe sus hiperparámetros sin --tune"
        )
    if model_params and (args.question == "P3" or args.model in ("seasonal", "persistence")):
        parser.error("Ese modelo no utiliza hiperparámetros de HGB o regresión logística")
    if "c" in model_params and not (args.question == "P2" and args.model == "logistic"):
        parser.error("C solo aplica a P2 con model=logistic")
    if args.model == "logistic" and set(model_params) - {"c", "max_iter"}:
        parser.error("Regresión logística recibe C y max_iter")
    if args.seed < 0 or args.seed >= 2**32 or args.n_clusters < 2:
        parser.error("La semilla debe estar entre 0 y 2**32-1; n_clusters debe ser al menos 2")
    for key, value in model_params.items():
        minimum = 0 if key == "l2_regularization" else 2 if key == "max_leaf_nodes" else 0
        if (
            not math.isfinite(value)
            or value < minimum
            or (value == 0 and key != "l2_regularization")
        ):
            parser.error(f"Valor inválido de {key}: {value}")
    if "c" in model_params:
        model_params["C"] = model_params.pop("c")
    verify_inputs()
    mlflow = configure_mlflow()
    context = run_context()
    print(f"Experimento: {cfg.EXPERIMENT_NAME} | commit: {context['git_commit'][:8]}", flush=True)
    if context["git_dirty"] == "true":
        print("Aviso: hay cambios sin commit; el commit registrado no describe el código exacto.")
    questions = list(RUNNERS) if args.question == "all" else [args.question]
    with project_run():
        for question in questions:
            kwargs = {
                "context": context,
                "register": not args.no_register,
                "figures_dir": args.figures_dir,
                "model_name": args.model,
                "seed": args.seed,
            }
            if question != "P3":
                kwargs["final_test"] = args.final_test
                kwargs["tune"] = args.tune
                kwargs["model_params"] = model_params
            else:
                kwargs["output_dir"] = args.figures_dir / "assignments"
                kwargs["n_clusters"] = args.n_clusters
            RUNNERS[question](**kwargs)
    print("\nListo. Tracking:", mlflow.get_tracking_uri())


if __name__ == "__main__":
    main()
