"""Pruebas del monitoreo de drift con Evidently, con tablas sintéticas."""

import json

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("evidently")

from mibici import config as cfg  # noqa: E402
from mibici import monitoring  # noqa: E402


def make_table(shift=0.0, new_stations=False, seed=0, rows_per_split=1200):
    """Tabla con particiones train, val y test; ``shift`` desplaza las variables numéricas."""
    rng = np.random.default_rng(seed)
    frames = []
    for index, split in enumerate(("train", "val", "test")):
        stations = np.arange(1, 21) + (20 if new_stations and split != "train" else 0)
        start = pd.Timestamp("2026-01-08", tz=cfg.TIMEZONE) + pd.Timedelta(days=60 * index)
        frame = pd.DataFrame(
            {
                "station_id": np.tile(stations, rows_per_split // 20).astype("int32"),
                "timestamp": np.repeat(
                    pd.date_range(start, periods=rows_per_split // 20, freq="h"), 20
                ),
                "split": split,
            }
        )
        frame["hour"] = rng.integers(0, 24, len(frame)).astype("int8")
        frame["weekday"] = rng.integers(0, 7, len(frame)).astype("int8")
        frame["is_weekend"] = (frame["weekday"] >= 5).astype("int8")
        frame["month"] = 3
        extra = shift if split != "train" else 0.0
        for column in cfg.P2_FEATURE_COLUMNS:
            if column not in frame:
                frame[column] = rng.normal(5 + extra, 1, len(frame))
        frame["virtual_occupancy"] = rng.uniform(0, 1, len(frame))
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def test_columns_exclude_month_and_include_station():
    for name in monitoring.SPECS:
        names = monitoring.columns(name)
        assert "month" not in names
        assert names[0] == "station_id"
    assert "virtual_occupancy" in monitoring.columns("p2")
    assert "virtual_occupancy" not in monitoring.columns("p1")


def test_split_sets_use_the_project_partitions():
    table = make_table()
    reference, current = monitoring.split_sets(table, "sep")
    assert set(reference["split"]) == {"train"}
    assert set(current["split"]) == {"test"}
    _, validation = monitoring.split_sets(table, "jul_ago")
    assert set(validation["split"]) == {"val"}


def test_prepare_has_text_categories_and_naive_dates():
    prepared = monitoring.prepare(make_table(), "p1")
    assert prepared["timestamp"].dt.tz is None
    for column in monitoring.CATEGORICAL:
        assert prepared[column].map(type).eq(str).all()
    assert "split" not in prepared


def test_p_value_tests_flag_drift_below_the_threshold_and_distances_above():
    assert monitoring.is_drifted("K-S p_value", 0.01, 0.05)
    assert not monitoring.is_drifted("K-S p_value", 0.20, 0.05)
    assert monitoring.is_drifted("Wasserstein distance (normed)", 0.10, 0.10)
    assert not monitoring.is_drifted("Jensen-Shannon distance", 0.05, 0.10)


def test_same_distribution_reports_no_drift():
    summary, _ = monitoring.compare("p1", make_table(), "sep")
    assert summary["variables_con_deriva"] == []
    assert summary["deriva_del_conjunto"] is False


def test_shifted_variables_are_reported_as_drift():
    summary, _ = monitoring.compare("p2", make_table(shift=3.0), "sep")
    flagged = set(summary["variables_con_deriva"])
    assert {"departures_lag_1", "departures_mean_168"} <= flagged
    assert "hour" not in flagged
    assert summary["deriva_del_conjunto"] is True
    row = next(r for r in summary["variables"] if r["variable"] == "departures_lag_1")
    assert row["media_actual"] > row["media_referencia"] + 2


def test_quality_counts_duplicates_and_missing_values():
    table = make_table()
    reference, _ = monitoring.split_sets(table, "sep")
    clean = monitoring.quality(reference, "p1")
    assert clean["valores_faltantes"] == 0
    assert clean["filas_duplicadas"] == 0
    broken = pd.concat([reference, reference.iloc[:5]], ignore_index=True)
    broken.loc[0, "departures_lag_1"] = np.nan
    result = monitoring.quality(broken, "p1")
    assert result["valores_faltantes"] == 1
    assert result["filas_duplicadas"] == 5


def test_new_stations_are_counted_with_their_row_share():
    reference, current = monitoring.split_sets(make_table(new_stations=True), "sep")
    result = monitoring.new_stations(reference, current)
    assert result["estaciones_nuevas"] == 20
    assert result["proporcion_de_filas"] == pytest.approx(1.0)


def test_monitor_writes_html_json_and_markdown(tmp_path):
    data_dir = tmp_path / "data"
    for name in monitoring.SPECS:
        path = cfg.data_path(cfg.FEATURE_FILES[name], data_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        make_table().to_parquet(path, index=False)
    output = tmp_path / "evidently"
    summary = monitoring.monitor(["p1"], ["sep"], data_dir, output)
    assert (output / "p1_sep.html").stat().st_size > 10_000
    saved = json.loads((output / "resumen.json").read_text(encoding="utf-8"))
    assert saved["comparaciones"][0]["conjunto"] == "p1"
    assert saved == json.loads(json.dumps(summary))
    text = (output / "resumen.md").read_text(encoding="utf-8")
    assert "entrenamiento contra septiembre 2026" in text
    assert "Filas duplicadas" in text


def test_main_without_html_writes_only_the_summary(tmp_path, capsys):
    data_dir = tmp_path / "data"
    path = cfg.data_path(cfg.FEATURE_FILES["p1"], data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    make_table().to_parquet(path, index=False)
    output = tmp_path / "out"
    monitoring.main(
        ["--dataset", "p1", "--data-dir", str(data_dir), "--output-dir", str(output), "--no-html"]
    )
    assert not list(output.glob("*.html"))
    assert (output / "resumen.json").is_file()
    assert "p1 contra sep" in capsys.readouterr().out
