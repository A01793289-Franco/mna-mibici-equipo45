"""Reproducibilidad del entrenamiento: misma semilla, mismos resultados.

Se comprueba en tres niveles:

1. Predicciones de cada fábrica de modelos de ``train.py`` entrenada dos veces.
2. Métricas registradas en MLflow por ``run_p1``, ``run_p2`` y ``run_p3`` ejecutados dos veces.
3. Artefactos: el CSV de grupos de P3 y los modelos guardados, cargados de nuevo.

Se excluyen las métricas de tiempo (``fit_seconds``, ``inference_seconds_per_1000``), que
dependen de la máquina y no de la semilla. El boosting usa la semilla solo en la partición de
early stopping; por eso estas pruebas lo activan, y una prueba de control confirma que otra
semilla sí cambia el resultado (si no cambiara, las demás pasarían sin probar nada).
"""

import numpy as np
import pytest

from mibici import config as cfg
from mibici import train

TIMING_METRICS = ("fit_seconds", "inference_seconds_per_1000")
EARLY_STOPPING = {"early_stopping": True, "validation_fraction": 0.2, "n_iter_no_change": 3}
P1_FEATURES = list(cfg.P1_FEATURE_COLUMNS)
P1_STATION_FEATURES = list(train.P1_FEATURE_COLUMNS_V2)
P2_FEATURES = list(cfg.P2_FEATURE_COLUMNS)


def deterministic(metrics):
    return {key: value for key, value in metrics.items() if key not in TIMING_METRICS}


def split(frame, name):
    return frame[frame.split == name]


def fit_predict(model, data, features, target):
    """Entrena con train y regresa ``(modelo, predicciones de val)``."""
    model.fit(split(data, "train")[features], split(data, "train")[target])
    return model, model.predict(split(data, "val")[features])


def station_model():
    step = "histgradientboostingregressor__"
    return train.make_demand_station_model().set_params(
        **{step + key: value for key, value in EARLY_STOPPING.items()}
    )


# ---------------------------------------------------------------------------
# Nivel 1: predicciones
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("build", "features"),
    [
        (lambda: train.make_demand_model(**EARLY_STOPPING), P1_FEATURES),
        (station_model, P1_STATION_FEATURES),
    ],
    ids=["hgb_poisson", "hgb_poisson_estacion"],
)
def test_demand_models_repeat_predictions_and_metrics(demand_data, build, features):
    predictions = [fit_predict(build(), demand_data, features, train.P1_TARGET)[1] for _ in "ab"]
    np.testing.assert_array_equal(predictions[0], predictions[1])
    truth = split(demand_data, "val")[train.P1_TARGET]
    first, second = (train.regression_metrics(truth, p, "val") for p in predictions)
    assert first == second


@pytest.mark.parametrize(
    "build",
    [lambda: train.make_risk_model(**EARLY_STOPPING), train.make_risk_baseline],
    ids=["hgb_clasificador", "logistica"],
)
def test_risk_models_repeat_classes_and_probabilities(risk_data, build):
    runs = [fit_predict(build(), risk_data, P2_FEATURES, train.P2_TARGET) for _ in "ab"]
    val = split(risk_data, "val")[P2_FEATURES]
    np.testing.assert_array_equal(runs[0][1], runs[1][1])
    np.testing.assert_array_equal(runs[0][0].predict_proba(val), runs[1][0].predict_proba(val))


def test_explicit_seed_is_reproducible_too(demand_data):
    predictions = [
        fit_predict(
            train.make_demand_model(random_state=7, **EARLY_STOPPING),
            demand_data,
            P1_FEATURES,
            train.P1_TARGET,
        )[1]
        for _ in "ab"
    ]
    np.testing.assert_array_equal(predictions[0], predictions[1])


def test_control_another_seed_changes_boosting(demand_data):
    """Control: si la semilla no influyera, las pruebas anteriores no probarían nada."""
    first, second = (
        fit_predict(
            train.make_demand_model(random_state=seed, **EARLY_STOPPING),
            demand_data,
            P1_FEATURES,
            train.P1_TARGET,
        )[1]
        for seed in (0, 1)
    )
    assert not np.array_equal(first, second)


def test_kmeans_repeats_labels_and_metrics(profile_tables):
    runs = [
        train.cluster_metrics(profile_tables["train"], profile_tables["val"], "kmeans")
        for _ in "ab"
    ]
    np.testing.assert_array_equal(runs[0][0], runs[1][0])
    assert runs[0][1] == runs[1][1]


# ---------------------------------------------------------------------------
# Niveles 2 y 3: runs de MLflow y artefactos
# ---------------------------------------------------------------------------
def assert_runs_match(mlflow, results, features, frame):
    """Compara métricas devueltas, métricas en MLflow y predicciones de los modelos guardados."""
    first, second = results
    assert first.keys() == second.keys()
    runs = mlflow.search_runs(search_all_experiments=True, output_format="list")
    for name in first:
        assert deterministic(first[name]) == deterministic(second[name]), name
        pair = sorted(
            (r for r in runs if r.info.run_name == name), key=lambda r: r.info.start_time
        )
        assert len(pair) == 2, name
        assert deterministic(pair[0].data.metrics) == deterministic(pair[1].data.metrics), name
        columns = features[name] if isinstance(features, dict) else features
        loaded = [mlflow.sklearn.load_model(f"runs:/{r.info.run_id}/model") for r in pair]
        np.testing.assert_array_equal(
            loaded[0].predict(frame[columns]), loaded[1].predict(frame[columns])
        )


def test_run_p1_twice_logs_the_same_metrics_and_models(
    mlflow_store, demand_data, run_context, tmp_path
):
    results = [
        train.run_p1(
            demand_data,
            figures_dir=tmp_path / f"figuras_{i}",
            context=run_context,
            register=False,
            model_params=EARLY_STOPPING,
        )
        for i in range(2)
    ]
    features = {
        "P1_estacional_h1": ["station_id", *P1_FEATURES],
        "P1_hgb_poisson_h1": P1_FEATURES,
        "P1_hgb_poisson_estacion_h1": P1_STATION_FEATURES,
    }
    assert_runs_match(mlflow_store, results, features, split(demand_data, "val"))


def test_run_p2_twice_logs_the_same_metrics_and_models(
    mlflow_store, risk_data, run_context, tmp_path
):
    results = [
        train.run_p2(
            risk_data,
            figures_dir=tmp_path / f"figuras_{i}",
            context=run_context,
            register=False,
            model_name="hgb",
            model_params=EARLY_STOPPING,
        )
        for i in range(2)
    ]
    assert_runs_match(mlflow_store, results, P2_FEATURES, split(risk_data, "val"))


def test_run_p3_twice_writes_identical_group_files(
    mlflow_store, profile_tables, run_context, tmp_path
):
    outputs = [tmp_path / "grupos_1", tmp_path / "grupos_2"]
    results = [
        train.run_p3(
            profile_tables,
            figures_dir=tmp_path / "figuras",
            output_dir=output,
            context=run_context,
            register=False,
            model_name="kmeans",
        )
        for output in outputs
    ]
    features = list(cfg.P3_FEATURE_COLUMNS)
    assert_runs_match(mlflow_store, results, features, profile_tables["val"])
    files = sorted(path.name for path in outputs[0].glob("*.csv"))
    assert files == ["p3_kmeans_perfil48.csv"]
    assert (outputs[0] / files[0]).read_bytes() == (outputs[1] / files[0]).read_bytes()
