import json
from types import SimpleNamespace

import mlflow
import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyRegressor

from mibici import abtest, config as cfg, train


@pytest.fixture
def temporal_data():
    parts = []
    for split, start, stations in [
        ("train", "2026-01-08", [1]),
        ("val", "2026-08-01", [1, 2]),
        ("test", "2026-09-01", [1, 2]),
    ]:
        for station in stations:
            timestamps = pd.date_range(start, periods=14 * 24, freq="h", tz=cfg.TIMEZONE)
            frame = pd.DataFrame({"station_id": station, "timestamp": timestamps, "split": split})
            for column in cfg.P1_FEATURE_COLUMNS:
                frame[column] = 1.0
            frame["target_departures"] = 1 + np.arange(len(frame)) % 3
            parts.append(frame)
    return pd.concat(parts, ignore_index=True)


def test_selects_the_same_sorted_september_rows_and_rejects_future_labels(temporal_data):
    rows = abtest.select_evaluation(temporal_data.sample(frac=1, random_state=3))
    assert rows["timestamp"].dt.month.eq(9).all()
    assert len(rows) == 14 * 24 * 2
    assert rows["station_id"].head(4).tolist() == [1, 2, 1, 2]
    altered = temporal_data.copy()
    altered.loc[altered["split"].eq("test"), "split"] = "train"
    with pytest.raises(ValueError, match="partición"):
        abtest.select_evaluation(altered)


def test_rejects_duplicated_station_hour_and_missing_target(temporal_data):
    duplicate = pd.concat([temporal_data, temporal_data.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicadas"):
        abtest.select_evaluation(duplicate)
    temporal_data.loc[0, "target_departures"] = np.nan
    with pytest.raises(ValueError, match="faltantes"):
        abtest.select_evaluation(temporal_data)


def test_training_cohort_and_count_come_from_the_registered_window(temporal_data):
    metadata = {
        "train_start": "2026-01-01",
        "train_end_exclusive": "2026-07-01",
        "training_rows": 14 * 24,
    }
    assert abtest.training_stations(temporal_data, metadata) == {1}
    with pytest.raises(ValueError, match="linaje"):
        abtest.training_stations(temporal_data, {**metadata, "training_rows": 1})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1])
def test_invalid_model_predictions_are_not_compared(temporal_data, value):
    class Invalid:
        def predict(self, frame):
            return np.full(len(frame), value)

    with pytest.raises(ValueError):
        abtest.checked_prediction(Invalid(), temporal_data, ["hour"])


def test_paired_bootstrap_is_reproducible_and_zero_when_models_are_identical(temporal_data):
    rows = abtest.select_evaluation(temporal_data)
    a = np.zeros(len(rows))
    b = np.ones(len(rows))
    first = abtest.paired_bootstrap(rows, a, b, repeats=200)
    assert first == abtest.paired_bootstrap(rows, a, b, repeats=200)
    assert first["mae_improvement_a_minus_b"] == pytest.approx(1)
    assert first["ci_low"] == pytest.approx(1)
    equal = abtest.paired_bootstrap(rows, a, a, repeats=200)
    assert equal["ci_low"] == equal["ci_high"] == 0


def test_bootstrap_rejects_a_gap_in_days(temporal_data):
    rows = abtest.select_evaluation(temporal_data)
    rows = rows.loc[rows["timestamp"].dt.day.ne(3)]
    with pytest.raises(ValueError, match="Faltan días"):
        abtest.paired_bootstrap(rows, np.zeros(len(rows)), np.ones(len(rows)), repeats=200)


def test_decision_uses_common_new_stations_and_conservative_tie_rule(temporal_data):
    rows = abtest.select_evaluation(temporal_data)
    a = rows["target_departures"].to_numpy(dtype=float) + 1
    b = a - 1
    result = abtest.compare_predictions(rows, a, b, {1}, repeats=200)
    assert result["segments"]["new"]["stations"] == 1
    assert result["decision"]["recommended"] == "challenger"
    assert result["decision"]["automatic_promotion"] is False
    tie = abtest.compare_predictions(rows, a, a, {1}, repeats=200)
    assert tie["decision"]["recommended"] == "champion"
    bad_new = b.copy()
    bad_new[rows["station_id"].eq(2)] += 3
    guarded = abtest.compare_predictions(rows, a, bad_new, {1}, repeats=200)
    assert guarded["decision"]["checks"]["new_stations_do_not_worsen"] is False


def test_zero_total_demand_is_undefined_wape_and_not_json_nan():
    result = abtest.metrics([0, 0], [0, 0])
    assert result["wape"] is None
    json.dumps(result, allow_nan=False)


def test_registry_versions_are_loaded_and_logged_without_moving_aliases(
    temporal_data, mlflow_store, run_context, tmp_path, monkeypatch
):
    client = mlflow.MlflowClient()
    name = train.REGISTERED_MODELS["P1"]
    columns = list(train.P1_FEATURE_COLUMNS_V2)
    for window, end, constant, alias in [
        (["train"], "2026-07-01", 0, "champion"),
        (["train", "val"], "2026-09-01", 2, "challenger"),
    ]:
        subset = temporal_data.loc[temporal_data["split"].isin(window)]
        model = DummyRegressor(strategy="constant", constant=constant).fit(
            subset[columns], subset[train.P1_TARGET]
        )
        with mlflow.start_run():
            mlflow.set_tags(run_context)
            mlflow.log_params(
                {
                    **run_context,
                    "rows_train": len(subset),
                    "train_start": "2026-01-01",
                    "train_end_exclusive": end,
                }
            )
            info = train.log_model(model, subset[columns])
            record = mlflow.register_model(info.model_uri, name)
            client.set_registered_model_alias(name, alias, record.version)
    monkeypatch.setattr(abtest, "run_context", lambda: run_context)
    data_dir = tmp_path / "data"
    (data_dir / "processed").mkdir(parents=True)
    temporal_data.to_parquet(data_dir / "processed/p1_hourly.parquet", index=False)
    output_dir = tmp_path / "output"
    result = abtest.compare_registered(data_dir=data_dir, output_dir=output_dir, repeats=200)
    assert result["models"]["A"]["uri"].endswith("/1")
    assert result["models"]["B"]["uri"].endswith("/2")
    assert result["decision"]["recommended"] == "challenger"
    assert result["evaluation"]["rows"] == 14 * 24 * 2
    assert (output_dir / "comparacion.png").exists()
    assert json.loads((output_dir / "resultados.json").read_text())["run_id"] == result["run_id"]
    logged = client.get_run(result["run_id"])
    assert logged.data.metrics["B_mae"] < logged.data.metrics["A_mae"]
    assert int(client.get_model_version_by_alias(name, "champion").version) == 1
    assert int(client.get_model_version_by_alias(name, "challenger").version) == 2
    with pytest.raises(ValueError, match="distintas"):
        abtest.compare_registered(
            data_dir=data_dir,
            output_dir=output_dir,
            champion_version=1,
            challenger_version=1,
            repeats=200,
        )
    with pytest.raises(ValueError, match="feature_version"):
        abtest.load_version(
            client, name, 1, "champion", {**run_context, "feature_version": "incompatible"}
        )


def test_model_trained_into_the_evaluation_period_is_rejected(run_context):
    class Client:
        def get_model_version_by_alias(self, name, alias):
            return SimpleNamespace(run_id="future-run")

        def get_run(self, run_id):
            return SimpleNamespace(
                data=SimpleNamespace(
                    params={
                        **run_context,
                        "train_end_exclusive": "2026-09-02",
                    }
                )
            )

    with pytest.raises(ValueError, match="anterior al periodo"):
        abtest.load_version(Client(), "mibici-p1-demanda", None, "challenger", run_context)
