"""Construye tablas reproducibles para P1-P3 sin ajustar modelos ni usar futuro en predictores."""

import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path

import numpy as np
import pandas as pd

from mibici import config as cfg
from mibici.dataset import canonical_hash, sha256_file, source_hash, verify_manifest, write_json


def local_time(value):
    """Convierte un límite de calendario a la zona horaria local de MiBici."""
    value = pd.Timestamp(value)
    return (
        value.tz_localize(cfg.TIMEZONE) if value.tzinfo is None else value.tz_convert(cfg.TIMEZONE)
    )


def load_events(manifest, data_dir):
    """Lee un mes a la vez y agrega eventos simultáneos; llegadas solo al finalizar el viaje."""
    parts = []
    for source in manifest["trips"]:
        trips = pd.read_parquet(Path(data_dir) / source["clean_path"])
        departures = trips[["origin_id", "started_at"]].rename(
            columns={"origin_id": "station_id", "started_at": "timestamp"}
        )
        departures = departures.assign(departures=1, arrivals=0)
        arrivals = trips[["destination_id", "ended_at"]].rename(
            columns={"destination_id": "station_id", "ended_at": "timestamp"}
        )
        arrivals = arrivals.assign(departures=0, arrivals=1)
        parts.append(pd.concat([departures, arrivals], ignore_index=True))
    events = pd.concat(parts, ignore_index=True)
    start, end = local_time(manifest["start"]), local_time(manifest["end_exclusive"])
    events = events[(events.timestamp >= start) & (events.timestamp < end)]
    events = (
        events.groupby(["station_id", "timestamp"], sort=True)[["departures", "arrivals"]]
        .sum()
        .reset_index()
    )
    events[["station_id", "departures", "arrivals"]] = events[
        ["station_id", "departures", "arrivals"]
    ].astype("int32")
    if events.empty:
        raise ValueError("No hay eventos dentro del periodo del manifiesto")
    return events


def hourly_counts(events, start, end):
    """P1-P3: completa horas tras la primera actividad, suponiendo operación continua posterior."""
    events = events.copy()
    events["timestamp"] = events.timestamp.dt.floor(cfg.FREQUENCY)
    counts = events.groupby(["station_id", "timestamp"])[["departures", "arrivals"]].sum()
    first_hour = events.groupby("station_id").timestamp.min()
    hours = pd.date_range(local_time(start), local_time(end), freq=cfg.FREQUENCY, inclusive="left")
    grid = pd.MultiIndex.from_product(
        [sorted(first_hour.index), hours], names=["station_id", "timestamp"]
    )
    frame = counts.reindex(grid, fill_value=0).reset_index()
    frame = frame[frame.timestamp >= frame.station_id.map(first_hour)].copy()
    frame[["station_id", "departures", "arrivals"]] = frame[
        ["station_id", "departures", "arrivals"]
    ].astype("int32")
    return frame.reset_index(drop=True)


def temporal_split(times, end=cfg.END_DATE_EXCLUSIVE):
    """Asigna P1-P2 por tiempo y excluye horizontes que rebasan los límites del conjunto."""
    target_end = times + pd.Timedelta(hours=cfg.HORIZON_HOURS)
    train_end, validation_end = local_time(cfg.TRAIN_END), local_time(cfg.VALIDATION_END)
    return pd.Series(
        np.select(
            [
                (times >= local_time(cfg.START_DATE)) & (target_end <= train_end),
                (times >= train_end) & (target_end <= validation_end),
                (times >= validation_end) & (target_end <= local_time(end)),
            ],
            ["train", "val", "test"],
            default="excluded",
        ),
        index=times.index,
        dtype="string",
    )


def p1_features(hourly, end=cfg.END_DATE_EXCLUSIVE):
    """P1: calendario conocido, rezagos y medias desplazadas; objetivo separado de los predictores."""
    frame = hourly.sort_values(["station_id", "timestamp"]).copy()
    frame["hour"] = frame.timestamp.dt.hour.astype("int8")
    frame["weekday"] = frame.timestamp.dt.dayofweek.astype("int8")
    frame["is_weekend"] = (frame.weekday >= 5).astype("int8")
    frame["month"] = frame.timestamp.dt.month.astype("int8")
    groups = frame.groupby("station_id", sort=False).departures
    for lag in cfg.LAGS_HOURS:
        frame[f"departures_lag_{lag}"] = groups.shift(lag)
    for window in cfg.ROLLING_HOURS:
        frame[f"departures_mean_{window}"] = groups.transform(
            lambda values: values.shift(1).rolling(window, min_periods=window).mean()
        )
    frame["target_departures"] = frame.departures
    frame["split"] = temporal_split(frame.timestamp, end)
    frame = frame.dropna(subset=list(cfg.P1_FEATURE_COLUMNS))
    frame = frame[frame.split != "excluded"]
    return frame[
        ["station_id", "timestamp", "split", *cfg.P1_FEATURE_COLUMNS, "target_departures"]
    ].reset_index(drop=True)


def virtual_occupancy(events, keys, stations, initial=cfg.INITIAL_OCCUPANCY):
    """P2: simula por evento con recorte y consulta el estado estrictamente anterior a cada límite."""
    if not 0 < initial < 1:
        raise ValueError("La ocupación inicial debe estar entre cero y uno")
    capacity = stations.set_index("station_id").capacity.to_dict()
    current, future = np.full(len(keys), np.nan), np.full(len(keys), np.nan)
    groups = events.sort_values(["station_id", "timestamp"]).groupby("station_id", sort=False)
    clipped = 0
    for station, rows in keys.groupby("station_id", sort=False).indices.items():
        if station not in capacity or station not in groups.indices:
            continue
        records = groups.get_group(station)
        deltas = (records.arrivals - records.departures).to_numpy()
        states = np.empty(len(deltas) + 1)
        states[0] = capacity[station] * initial
        for i, change in enumerate(deltas):
            value = states[i] + change
            clipped += int(value < 0 or value > capacity[station])
            states[i + 1] = min(capacity[station], max(0, value))
        ticks = pd.DatetimeIndex(records.timestamp).as_unit("ns").asi8
        queries = pd.DatetimeIndex(keys.iloc[rows].timestamp).as_unit("ns").asi8
        next_queries = queries + pd.Timedelta(hours=cfg.HORIZON_HOURS).value
        current[rows] = states[np.searchsorted(ticks, queries, side="left")] / capacity[station]
        future[rows] = (
            states[np.searchsorted(ticks, next_queries, side="left")] / capacity[station]
        )
    return current, future, clipped


def p2_features(p1, hourly, events, stations, initial=cfg.INITIAL_OCCUPANCY):
    """P2: añade estado virtual actual y flujos pasados; la ocupación futura solo define la etiqueta."""
    frame = p1[["station_id", "timestamp", "split", *cfg.P1_FEATURE_COLUMNS]].copy()
    flows = hourly.sort_values(["station_id", "timestamp"]).copy()
    flows["net_flow"] = flows.arrivals - flows.departures
    names = []
    for lag in cfg.NET_FLOW_LAGS_HOURS:
        name = f"net_flow_lag_{lag}"
        names.append(name)
        flows[name] = flows.groupby("station_id", sort=False).net_flow.shift(lag)
    frame = frame.merge(
        flows[["station_id", "timestamp", *names]],
        on=["station_id", "timestamp"],
        validate="one_to_one",
    )
    current, future, clipped = virtual_occupancy(
        events, frame[["station_id", "timestamp"]], stations, initial
    )
    frame["virtual_occupancy"] = current
    frame["target_risk"] = np.select(
        [future <= cfg.LOW_OCCUPANCY, future >= cfg.HIGH_OCCUPANCY], [1, 2], default=0
    ).astype("int8")
    frame = frame.dropna(subset=list(cfg.P2_FEATURE_COLUMNS))
    return frame.reset_index(drop=True), {
        "clipped_events": clipped,
        "excluded_rows_without_capacity_or_history": len(p1) - len(frame),
    }


def station_profiles(hourly, stations, start, end, min_days=cfg.MIN_PROFILE_DAYS):
    """P3: compara la forma de 48 medias horarias sin que domine el volumen total.

    Excluye el primer día parcial, la cobertura insuficiente y los perfiles nulos.
    """
    first_day = hourly.groupby("station_id").timestamp.min().dt.normalize() + pd.Timedelta(days=1)
    frame = hourly[
        (hourly.timestamp >= local_time(start)) & (hourly.timestamp < local_time(end))
    ].copy()
    frame = frame[frame.timestamp >= frame.station_id.map(first_day)]
    frame["day"] = frame.timestamp.dt.normalize()
    days = frame.groupby("station_id").day.nunique()
    frame["kind"] = np.where(frame.timestamp.dt.dayofweek >= 5, "weekend", "weekday")
    frame["hour"] = frame.timestamp.dt.hour
    values = (
        frame.groupby(["station_id", "kind", "hour"]).departures.mean().unstack(["kind", "hour"])
    )
    values.columns = [f"{kind}_{hour:02d}" for kind, hour in values.columns]
    values = values.reindex(columns=list(cfg.P3_FEATURE_COLUMNS))
    values = values.loc[
        days.reindex(values.index).ge(min_days)
        & values.notna().all(axis=1)
        & (values.sum(axis=1) > 0)
    ]
    values = values.div(values.sum(axis=1), axis=0)
    values["observed_days"] = days.reindex(values.index)
    return values.reset_index().merge(
        stations[["station_id", "name", "latitude", "longitude"]],
        on="station_id",
        validate="one_to_one",
    )


def verify_features(manifest, data_dir, source_version):
    """Comprueba versión de origen, código y hashes para detectar variables desactualizadas."""
    payload = {
        key: value
        for key, value in manifest.items()
        if key not in ("feature_version", "created_at")
    }
    if (
        canonical_hash(payload) != manifest["feature_version"]
        or manifest["data_version"] != source_version
    ):
        raise ValueError("La versión de variables no coincide con el manifiesto de origen")
    if manifest["features_sha256"] != source_hash(__file__) or manifest[
        "config_sha256"
    ] != source_hash(cfg.__file__):
        raise ValueError("La configuración o el código cambió: reconstruye las variables")
    for item in manifest["files"].values():
        path = Path(data_dir) / item["path"]
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError(f"Archivo de variables ausente o modificado: {path}")


def build_features(
    data_dir=cfg.DATA_DIR,
    manifest_path=cfg.MANIFEST_PATH,
    output_manifest=cfg.FEATURE_MANIFEST_PATH,
    initial=cfg.INITIAL_OCCUPANCY,
):
    """Genera P1, P2 y perfiles P3 por partición desde los Parquet verificados de ingesta."""
    source = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    verify_manifest(source, data_dir)
    stations = pd.read_parquet(Path(data_dir) / source["stations"]["clean_path"])
    print("Agregando eventos y horas...", flush=True)
    events = load_events(source, data_dir)
    hourly = hourly_counts(events, source["start"], source["end_exclusive"])
    print("Construyendo variables P1 y P2...", flush=True)
    p1 = p1_features(hourly, source["end_exclusive"])
    p2, diagnostics = p2_features(p1, hourly, events, stations, initial)
    if p1.empty or p2.empty:
        raise ValueError("No hay filas con suficiente historia para P1/P2")
    tables = {"p1": p1, "p2": p2}
    for name, start, end in [
        ("train", source["start"], cfg.TRAIN_END),
        ("val", cfg.TRAIN_END, cfg.VALIDATION_END),
        ("test", cfg.VALIDATION_END, source["end_exclusive"]),
    ]:
        tables[f"p3_{name}"] = station_profiles(hourly, stations, start, end)
    files = {}
    for name, frame in tables.items():
        target = cfg.data_path(cfg.FEATURE_FILES[name], data_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        frame.to_parquet(temporary, index=False, compression="snappy")
        temporary.replace(target)
        files[name] = {
            "path": target.relative_to(data_dir).as_posix(),
            "sha256": sha256_file(target),
            "rows": len(frame),
        }
    payload = {
        "data_version": source["data_version"],
        "features_sha256": source_hash(__file__),
        "config_sha256": source_hash(cfg.__file__),
        "packages": {name: version(name) for name in ("pandas", "numpy", "pyarrow")},
        "initial_occupancy": initial,
        "predictors": {
            "p1": list(cfg.P1_FEATURE_COLUMNS),
            "p2": list(cfg.P2_FEATURE_COLUMNS),
            "p3": list(cfg.P3_FEATURE_COLUMNS),
        },
        "split_counts": {
            name: {
                str(key): int(value) for key, value in tables[name].split.value_counts().items()
            }
            for name in ("p1", "p2")
        },
        "p2_class_counts": {
            cfg.P2_CLASS_NAMES[int(key)]: int(value)
            for key, value in p2.target_risk.value_counts().items()
        },
        "coverage_policy": "Horas completas desde primera actividad; operación continua supuesta; P3 excluye primer día parcial y exige cobertura mínima.",
        "p2_diagnostics": diagnostics,
        "files": files,
    }
    result = {**payload, "feature_version": canonical_hash(payload)}
    previous = (
        json.loads(Path(output_manifest).read_text(encoding="utf-8"))
        if Path(output_manifest).exists()
        else {}
    )
    result["created_at"] = (
        previous.get("created_at")
        if previous.get("feature_version") == result["feature_version"]
        else datetime.now(timezone.utc).isoformat()
    )
    verify_features(result, data_dir, source["data_version"])
    write_json(output_manifest, result)
    print(json.dumps({name: item["rows"] for name, item in files.items()}, indent=2), flush=True)
    print(f"Versión de variables: {result['feature_version']}", flush=True)
    return result


def main():
    """Expone construcción y comprobación de variables en Windows, macOS y Linux."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir", type=Path, default=cfg.DATA_DIR, help="Carpeta local utilizada en la ingesta"
    )
    parser.add_argument(
        "--initial-occupancy",
        type=float,
        default=cfg.INITIAL_OCCUPANCY,
        help="Proporción inicial del inventario virtual para sensibilidad P2",
    )
    parser.add_argument(
        "--verify", action="store_true", help="Comprobar hashes, versiones de origen y código"
    )
    args = parser.parse_args()
    if args.verify:
        source = json.loads(cfg.MANIFEST_PATH.read_text(encoding="utf-8"))
        verify_manifest(source, args.data_dir)
        verify_features(
            json.loads(cfg.FEATURE_MANIFEST_PATH.read_text(encoding="utf-8")),
            args.data_dir,
            source["data_version"],
        )
        print("Variables y versiones verificadas.")
    else:
        build_features(args.data_dir, initial=args.initial_occupancy)


if __name__ == "__main__":
    main()
