"""Pruebas de la validación con DeepChecks sobre tablas sintéticas con el esquema real.

Una tabla limpia debe aprobar; cada defecto inyectado (nulos, duplicados, rangos, tipos,
partición) debe hacer fallar la suite bloqueante correspondiente. El drift solo se reporta.
Se omiten si deepchecks no está instalado (``requirements-validation.txt``).
"""

from importlib.util import find_spec
import json

import numpy as np
import pandas as pd
import pytest

# No se usa importorskip: importaría deepchecks antes de que validation aplique la compatibilidad.
if find_spec("deepchecks") is None:
    pytest.skip("requiere requirements-validation.txt", allow_module_level=True)

from mibici import config as cfg  # noqa: E402
from mibici import validation  # noqa: E402
from mibici.features import temporal_split  # noqa: E402

PERIODS = {"train": "2026-03-02", "val": "2026-07-13", "test": "2026-09-07"}


def p1_table(seed=0, hours=24 * 8, stations=(1, 2)):
    """Tabla P1 coherente: calendario derivado de timestamp, conteos enteros y split real."""
    rng = np.random.default_rng(seed)
    frames = []
    for start in PERIODS.values():
        times = pd.date_range(start, periods=hours, freq="h", tz=cfg.TIMEZONE)
        for station in stations:
            frames.append(pd.DataFrame({"station_id": station, "timestamp": times}))
    frame = pd.concat(frames, ignore_index=True)
    frame["station_id"] = frame.station_id.astype("int32")
    frame["timestamp"] = frame.timestamp.dt.as_unit("us")
    frame["split"] = temporal_split(frame.timestamp)
    frame["hour"] = frame.timestamp.dt.hour.astype("int8")
    frame["weekday"] = frame.timestamp.dt.dayofweek.astype("int8")
    frame["is_weekend"] = (frame.weekday >= 5).astype("int8")
    frame["month"] = frame.timestamp.dt.month.astype("int8")
    for column in cfg.P1_FEATURE_COLUMNS[4:]:
        frame[column] = rng.poisson(2, len(frame)).astype("float64")
    frame["target_departures"] = rng.poisson(2, len(frame)).astype("int32")
    return frame


def tables(frame):
    return {split: frame[frame.split == split] for split in PERIODS}


def failed_checks(result):
    return {
        check["check"]
        for suite in result["suites"]
        if suite["bloqueante"]
        for check in suite["checks"]
        if check["estado"] != "aprobado"
    }


@pytest.fixture
def clean():
    return p1_table()


def test_clean_table_passes_every_blocking_suite(clean):
    result = validation.validate_dataset("p1", tables(clean))
    assert result["aprobado"], failed_checks(result)
    assert result["filas"] == {"train": 384, "val": 384, "test": 384}
    suites = {(s["suite"], s["comparacion"]) for s in result["suites"]}
    assert suites == {
        ("integridad", "completo"),
        ("particion", "train-val"),
        ("particion", "train-test"),
        ("drift", "train-val"),
        ("drift", "train-test"),
    }


@pytest.mark.parametrize(
    ("damage", "expected"),
    [
        (
            lambda d: d.assign(departures_lag_1=d.departures_lag_1.mask(d.index == 5)),
            "PercentOfNulls",
        ),
        (lambda d: pd.concat([d, d.iloc[[0]]]), "DataDuplicates"),
        (lambda d: d.assign(hour=d.hour.mask(d.index == 3, 25)), "ValueRules"),
        (
            lambda d: d.assign(departures_lag_24=d.departures_lag_24.mask(d.index == 7, -1)),
            "ValueRules",
        ),
        (lambda d: d.assign(is_weekend=(1 - d.is_weekend).astype("int8")), "ValueRules"),
        (lambda d: d.assign(station_id=d.station_id.astype("int64")), "ExpectedDtypes"),
        (
            lambda d: d.assign(target_departures=d.target_departures.astype("float64")),
            "ExpectedDtypes",
        ),
    ],
    ids=[
        "nulo",
        "fila-duplicada",
        "hora-25",
        "conteo-negativo",
        "fin-de-semana",
        "tipo-id",
        "tipo-objetivo",
    ],
)
def test_injected_defect_fails_integrity(clean, damage, expected):
    result = validation.validate_dataset("p1", tables(damage(clean).reset_index(drop=True)))
    assert not result["aprobado"]
    assert expected in failed_checks(result)


def test_row_in_the_wrong_split_is_detected(clean):
    damaged = clean.copy()
    damaged.loc[damaged.split.eq("train").idxmax(), "split"] = "test"
    result = validation.validate_dataset("p1", tables(damaged))
    assert not result["aprobado"]
    assert {"ValueRules", "DateTrainTestLeakageOverlap"} <= failed_checks(result)


def test_duplicated_station_hour_with_different_values_is_detected(clean):
    copy = clean.iloc[[0]].assign(target_departures=np.int32(99))
    result = validation.validate_dataset("p1", tables(pd.concat([clean, copy], ignore_index=True)))
    assert "DataDuplicates" in failed_checks(result)


def test_drift_is_reported_but_does_not_block(clean):
    shifted = clean.copy()
    test_rows = shifted.split == "test"
    shifted.loc[test_rows, "departures_lag_1"] += 50
    result = validation.validate_dataset("p1", tables(shifted))
    assert result["aprobado"]
    drift = next(
        s for s in result["suites"] if s["suite"] == "drift" and s["comparacion"] == "train-test"
    )
    feature_drift = next(c for c in drift["checks"] if c["check"] == "FeatureDrift")
    assert feature_drift["estado"] == "fallido"
    assert feature_drift["drift_por_variable"]["departures_lag_1"] > 0.5
    assert "month" not in feature_drift["drift_por_variable"]


def test_p3_profiles_must_be_normalized():
    from tests.test_train import profile_table

    split_tables = {}
    for seed, split in enumerate(PERIODS):
        table = profile_table(seed=seed)
        table["observed_days"] = np.arange(len(table), dtype="int64") + cfg.MIN_PROFILE_DAYS
        table["name"] = table.name.astype("string")
        table[["latitude", "longitude"]] = table[["latitude", "longitude"]].astype("Float64")
        split_tables[split] = table
    assert validation.validate_dataset("p3", split_tables)["aprobado"]
    split_tables["val"].loc[0, "weekday_08"] += 0.5
    result = validation.validate_dataset("p3", split_tables)
    assert "ValueRules" in failed_checks(result)


def write_processed(data_dir, frame):
    path = cfg.data_path(cfg.FEATURE_FILES["p1"], data_dir)
    path.parent.mkdir(parents=True)
    frame.to_parquet(path, index=False)


def test_cli_writes_versioned_summary_and_exits_zero(tmp_path, clean):
    write_processed(tmp_path / "data", clean)
    output = tmp_path / "reporte"
    validation.main(
        ["--dataset", "p1", "--data-dir", str(tmp_path / "data"), "--output-dir", str(output)]
    )
    summary = json.loads((output / "resumen.json").read_text(encoding="utf-8"))
    assert summary["aprobado"] is True
    assert summary["semilla"] == cfg.SEED
    assert list(summary["conjuntos"]) == ["p1"]
    assert "| p1 | integridad |" in (output / "resumen.md").read_text(encoding="utf-8")
    assert not (output / "html").exists()


def test_cli_exits_with_error_when_blocking_suite_fails(tmp_path, clean):
    write_processed(tmp_path / "data", clean.assign(hour=np.int8(30)))
    with pytest.raises(SystemExit) as stop:
        validation.main(
            [
                "--dataset",
                "p1",
                "--data-dir",
                str(tmp_path / "data"),
                "--output-dir",
                str(tmp_path / "r"),
            ]
        )
    assert stop.value.code == 1
