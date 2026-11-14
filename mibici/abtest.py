import argparse
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
import math
from pathlib import Path

import mlflow
from mlflow.exceptions import MlflowException
import numpy as np
import pandas as pd

from mibici import config as cfg
from mibici.dataset import verify_manifest, write_json
from mibici.features import temporal_split, verify_features
from mibici.train import REGISTERED_MODELS, configure_mlflow, regression_metrics, run_context

OUTPUT_DIR = cfg.ROOT_DIR / "reports" / "abtest"
BOOTSTRAP_REPEATS = 5000
BLOCK_DAYS = 7
POLICY = "MAE menor, IC95 de mejora positivo, RMSE y MAE de estaciones nuevas sin empeorar"


def verify_data(data_dir):
    source = json.loads(cfg.MANIFEST_PATH.read_text(encoding="utf-8"))
    features = json.loads(cfg.FEATURE_MANIFEST_PATH.read_text(encoding="utf-8"))
    verify_manifest(source, data_dir)
    verify_features(features, data_dir, source["data_version"])


def local_times(values):
    times = pd.to_datetime(values)
    return (
        times.dt.tz_localize(cfg.TIMEZONE)
        if times.dt.tz is None
        else times.dt.tz_convert(cfg.TIMEZONE)
    )


def select_evaluation(table):
    required = {"station_id", "timestamp", "split", "target_departures"}
    if required - set(table):
        raise ValueError(f"Faltan columnas: {sorted(required - set(table))}")
    if table[list(required)].isna().any().any():
        raise ValueError("Hay valores faltantes en claves, partición u objetivo")
    times = local_times(table["timestamp"])
    if not temporal_split(times).eq(table["split"]).all():
        raise ValueError("Las etiquetas de partición no coinciden con las fechas y el horizonte")
    if table.duplicated(["station_id", "timestamp"]).any():
        raise ValueError("Hay claves estación-hora duplicadas")
    if not np.isfinite(table["target_departures"]).all() or (table["target_departures"] < 0).any():
        raise ValueError("La demanda observada debe ser finita y no negativa")
    result = table.loc[table["split"].eq("test")].copy()
    result["timestamp"] = times.loc[result.index]
    if result.empty:
        raise ValueError("No hay filas del periodo actual de septiembre")
    return result.sort_values(["timestamp", "station_id"]).reset_index(drop=True)


def training_stations(table, metadata):
    if not metadata["train_start"]:
        raise ValueError("El modelo no acredita el inicio de su entrenamiento")
    start = pd.Timestamp(metadata["train_start"], tz=cfg.TIMEZONE)
    end = pd.Timestamp(metadata["train_end_exclusive"], tz=cfg.TIMEZONE)
    times = local_times(table["timestamp"])
    mask = (times >= start) & (times + pd.Timedelta(hours=cfg.HORIZON_HOURS) <= end)
    if int(mask.sum()) != metadata["training_rows"]:
        raise ValueError("Las filas de entrenamiento no coinciden con el linaje del modelo")
    return set(table.loc[mask, "station_id"])


def checked_prediction(model, frame, columns):
    missing = set(columns) - set(frame)
    if missing:
        raise ValueError(f"Faltan variables de la firma: {sorted(missing)}")
    values = frame[columns]
    if not np.isfinite(values.to_numpy(dtype=float)).all():
        raise ValueError("Los predictores deben ser finitos y estar completos")
    prediction = np.asarray(model.predict(values), dtype=float)
    if prediction.shape != (len(frame),) or not np.isfinite(prediction).all():
        raise ValueError("El modelo no produjo una predicción finita por fila")
    if (prediction < 0).any():
        raise ValueError("El modelo produjo demanda negativa")
    return prediction


def metrics(y_true, prediction):
    values = regression_metrics(y_true, prediction, "eval")
    return {
        key.removeprefix("eval_"): value if math.isfinite(value) else None
        for key, value in values.items()
    }


def paired_bootstrap(frame, a, b, repeats=BOOTSTRAP_REPEATS, block_days=BLOCK_DAYS, seed=cfg.SEED):
    if repeats < 100 or seed < 0 or seed >= 2**32:
        raise ValueError("Usa al menos 100 réplicas y una semilla entre 0 y 2**32-1")
    daily = (
        pd.DataFrame(
            {
                "day": frame["timestamp"].dt.strftime("%Y-%m-%d"),
                "error_a": np.abs(frame["target_departures"].to_numpy() - a),
                "error_b": np.abs(frame["target_departures"].to_numpy() - b),
                "rows": 1,
            }
        )
        .groupby("day", sort=True)
        .sum()
    )
    count = len(daily)
    if block_days < 1 or block_days > count or count < 2:
        raise ValueError("El bloque debe caber en un periodo de al menos dos días")
    expected = pd.date_range(daily.index[0], daily.index[-1], freq="D").strftime("%Y-%m-%d")
    if list(expected) != list(daily.index):
        raise ValueError("Faltan días completos en el periodo de evaluación")
    rng = np.random.default_rng(seed)
    starts = rng.integers(count, size=(repeats, math.ceil(count / block_days)))
    indices = ((starts[:, :, None] + np.arange(block_days)) % count).reshape(repeats, -1)
    indices = indices[:, :count]
    delta = (daily["error_a"] - daily["error_b"]).to_numpy()
    estimates = delta[indices].sum(axis=1) / daily["rows"].to_numpy()[indices].sum(axis=1)
    low, high = np.quantile(estimates, [0.025, 0.975])
    return {
        "method": "paired_circular_day_blocks",
        "block_days": block_days,
        "repeats": repeats,
        "seed": seed,
        "confidence": 0.95,
        "mae_improvement_a_minus_b": float(delta.sum() / daily["rows"].sum()),
        "ci_low": float(low),
        "ci_high": float(high),
        "daily": [
            {
                "date": day,
                "rows": int(row.rows),
                "mae_a": float(row.error_a / row.rows),
                "mae_b": float(row.error_b / row.rows),
            }
            for day, row in daily.iterrows()
        ],
    }


def compare_predictions(frame, a, b, reference_stations, **bootstrap):
    y_true = frame["target_departures"].to_numpy()
    overall = {"A": metrics(y_true, a), "B": metrics(y_true, b)}
    segments = {}
    known = frame["station_id"].isin(reference_stations).to_numpy()
    for label, mask in (("known", known), ("new", ~known)):
        if mask.any():
            segments[label] = {
                "rows": int(mask.sum()),
                "stations": int(frame.loc[mask, "station_id"].nunique()),
                "A": metrics(y_true[mask], a[mask]),
                "B": metrics(y_true[mask], b[mask]),
            }
    interval = paired_bootstrap(frame, a, b, **bootstrap)
    checks = {
        "mae_improves": overall["B"]["mae"] < overall["A"]["mae"],
        "ci_excludes_no_improvement": interval["ci_low"] > 0,
        "rmse_does_not_worsen": overall["B"]["rmse"] <= overall["A"]["rmse"],
        "new_stations_do_not_worsen": (
            "new" not in segments or segments["new"]["B"]["mae"] <= segments["new"]["A"]["mae"]
        ),
    }
    denominator = overall["A"]["mae"]
    return {
        "metrics": overall,
        "segments": segments,
        "uncertainty": interval,
        "relative_mae_improvement": (
            (overall["A"]["mae"] - overall["B"]["mae"]) / denominator if denominator else None
        ),
        "decision": {
            "policy": POLICY,
            "checks": checks,
            "recommended": "challenger" if all(checks.values()) else "champion",
            "automatic_promotion": False,
        },
    }


def load_version(client, name, requested_version, alias, context):
    record = (
        client.get_model_version(name, str(requested_version))
        if requested_version
        else client.get_model_version_by_alias(name, alias)
    )
    run = client.get_run(record.run_id)
    params = run.data.params
    end = params.get("train_end_exclusive")
    if not end or pd.Timestamp(end) > pd.Timestamp(cfg.VALIDATION_END):
        raise ValueError("No se acredita un entrenamiento anterior al periodo de evaluación")
    for key in ("data_version", "feature_version"):
        if params.get(key) != context[key] or context[key] == "no disponible":
            raise ValueError(f"El modelo y la evaluación no comparten {key}")
    uri = f"models:/{name}/{record.version}"
    info = mlflow.models.get_model_info(uri)
    if info.signature is None or info.signature.inputs is None:
        raise ValueError("El modelo registrado no tiene firma de entrada")
    columns = list(info.signature.inputs.input_names())
    model = mlflow.sklearn.load_model(uri)
    return (
        model,
        columns,
        {
            "name": name,
            "version": int(record.version),
            "uri": uri,
            "requested_alias": None if requested_version else alias,
            "run_id": record.run_id,
            "train_start": params.get("train_start"),
            "train_end_exclusive": end,
            "training_rows": int(params["rows_train"]),
            "git_commit": run.data.tags.get("git_commit"),
            "data_version": params["data_version"],
            "feature_version": params["feature_version"],
            "columns": columns,
        },
    )


def plot_comparison(result, path):
    import matplotlib.pyplot as plt

    daily = result["uncertainty"]["daily"]
    figure, axes = plt.subplots(1, 2, figsize=(10, 3.4))
    for key, label, color in (("a", "A: champion", "#164c69"), ("b", "B: challenger", "#b46e18")):
        axes[0].plot(
            [int(row["date"][-2:]) for row in daily],
            [row[f"mae_{key}"] for row in daily],
            label=label,
            color=color,
        )
    axes[0].set(xlabel="Día de septiembre", ylabel="MAE por estación-hora")
    axes[0].legend(fontsize=8)
    labels = list(result["segments"])
    positions = np.arange(len(labels))
    for offset, key, label, color in ((-0.18, "A", "A", "#164c69"), (0.18, "B", "B", "#b46e18")):
        axes[1].bar(
            positions + offset,
            [result["segments"][s][key]["mae"] for s in labels],
            width=0.36,
            label=label,
            color=color,
        )
    axes[1].set_xticks(positions, ["Conocidas" if s == "known" else "Nuevas" for s in labels])
    axes[1].set(ylabel="MAE", title="Estaciones respecto al entrenamiento de A")
    axes[1].legend(fontsize=8)
    figure.suptitle("P1: comparación offline sobre las mismas filas de septiembre")
    figure.tight_layout()
    figure.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(figure)


def markdown_result(result):
    a, b = result["models"]["A"], result["models"]["B"]
    lines = [
        "# A/B offline de P1",
        "",
        result["scope"],
        "",
        f"- Run de comparación: `{result['run_id']}`.",
        f"- Evaluación común: {result['evaluation']['rows']:,} filas, "
        f"{result['evaluation']['stations']} estaciones.",
        f"- A: `{a['uri']}`, entrenamiento hasta {a['train_end_exclusive']} (exclusivo).",
        f"- B: `{b['uri']}`, entrenamiento hasta {b['train_end_exclusive']} (exclusivo).",
        "",
        "| Modelo | MAE | RMSE | WAPE | R² |",
        "|---|---|---|---|---|",
    ]
    for key in ("A", "B"):
        m = result["metrics"][key]
        values = [
            "no definido" if m[name] is None else f"{m[name]:.6f}"
            for name in ("mae", "rmse", "wape", "r2")
        ]
        lines.append(f"| {key} | " + " | ".join(values) + " |")
    lines += [
        "",
        "WAPE se expresa como proporción; multiplicar por 100 para porcentaje.",
        "",
        "| Segmento respecto a A | Filas | Estaciones | MAE A | MAE B |",
        "|---|---|---|---|---|",
    ]
    for name, segment in result["segments"].items():
        lines.append(
            f"| {name} | {segment['rows']:,} | {segment['stations']} | "
            f"{segment['A']['mae']:.6f} | {segment['B']['mae']:.6f} |"
        )
    uncertainty = result["uncertainty"]
    lines += [
        "",
        f"Mejora MAE A-B: {uncertainty['mae_improvement_a_minus_b']:.6f}; "
        f"IC 95% [{uncertainty['ci_low']:.6f}, {uncertainty['ci_high']:.6f}].",
        f"Bootstrap pareado circular: bloques de {uncertainty['block_days']} días, "
        f"{uncertainty['repeats']} réplicas, semilla {uncertainty['seed']}.",
        "",
        f"Regla: {POLICY}.",
        f"Versión recomendada: **{result['decision']['recommended']}**. "
        "La comparación no modifica ningún alias.",
        "",
    ]
    lines.extend(
        f"- {name}: {'cumple' if passed else 'no cumple'}."
        for name, passed in result["decision"]["checks"].items()
    )
    lines += [
        "",
        "![Error por día y por segmento](comparacion.png)",
        "",
        "## Alcance y Continuous Training",
        "",
        "Es una comparación offline retrospectiva, no un experimento de tráfico aleatorio. "
        "Septiembre ya se había observado en entregas anteriores y en el entrenamiento del "
        "challenger; ninguna versión lo usó para ajustar sus pesos. No se cambian "
        "hiperparámetros después de esta comparación. El intervalo describe la variabilidad "
        "del mes bajo bloques semanales; no demuestra generalización a meses futuros.",
        "",
        "Mantener monitoreo mensual y revisar calidad antes de entrenar. Un cambio de "
        "station_id o de demanda reciente abre una revisión; no mueve champion por sí solo. "
        "Entrenar con información anterior al nuevo periodo de evaluación, comparar con "
        "MAE y los controles de RMSE/estaciones nuevas, y promover una versión solo con "
        "evidencia favorable en un periodo posterior. Conservar la versión previa para "
        "revertir si empeora la operación.",
        "",
    ]
    return "\n".join(lines)


def compare_registered(
    name=REGISTERED_MODELS["P1"],
    data_dir=cfg.DATA_DIR,
    output_dir=OUTPUT_DIR,
    champion_version=None,
    challenger_version=None,
    seed=cfg.SEED,
    repeats=BOOTSTRAP_REPEATS,
    block_days=BLOCK_DAYS,
):
    client = mlflow.MlflowClient()
    context = run_context()
    loaded = {
        key: load_version(client, name, number, alias, context)
        for key, number, alias in (
            ("A", champion_version, "champion"),
            ("B", challenger_version, "challenger"),
        )
    }
    if loaded["A"][2]["version"] == loaded["B"][2]["version"]:
        raise ValueError("A y B deben ser dos versiones distintas del mismo modelo")
    path = cfg.data_path(cfg.FEATURE_FILES["p1"], data_dir)
    table = pd.read_parquet(path)
    frame = select_evaluation(table)
    predictions = {
        key: checked_prediction(model, frame, columns)
        for key, (model, columns, _) in loaded.items()
    }
    columns = list(
        dict.fromkeys(
            ["station_id", "timestamp", "target_departures", *loaded["A"][1], *loaded["B"][1]]
        )
    )
    digest = sha256(pd.util.hash_pandas_object(frame[columns], index=False).to_numpy().tobytes())
    cohorts = {key: training_stations(table, metadata) for key, (_, _, metadata) in loaded.items()}
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Comparación offline retrospectiva de versiones registradas de P1.",
        "context": context,
        "models": {key: metadata for key, (_, _, metadata) in loaded.items()},
        "evaluation": {
            "rows": len(frame),
            "stations": int(frame["station_id"].nunique()),
            "start": frame["timestamp"].min().isoformat(),
            "end": frame["timestamp"].max().isoformat(),
            "sha256": digest.hexdigest(),
            "table_sha256": sha256(path.read_bytes()).hexdigest(),
        },
        "packages": {
            package: version(package)
            for package in ("mlflow", "scikit-learn", "numpy", "pandas", "pyarrow")
        },
        **compare_predictions(
            frame,
            predictions["A"],
            predictions["B"],
            cohorts["A"],
            repeats=repeats,
            block_days=block_days,
            seed=seed,
        ),
    }
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with mlflow.start_run(run_name="P1_AB_champion_challenger_sep") as run:
        result["run_id"] = run.info.run_id
        mlflow.set_tags(
            {
                **context,
                "equipo": cfg.TEAM,
                "question": "p1",
                "stage_of_work": "offline_ab",
                "evaluation_scope": "retrospective",
            }
        )
        mlflow.log_params(
            {
                "model_name": name,
                "version_a": loaded["A"][2]["version"],
                "version_b": loaded["B"][2]["version"],
                "seed": seed,
                "block_days": block_days,
                "bootstrap_repeats": repeats,
                "rows": len(frame),
                "evaluation_sha256": digest.hexdigest(),
                "decision_policy": POLICY,
            }
        )
        mlflow.log_metrics(
            {
                f"{key}_{metric}": value
                for key, values in result["metrics"].items()
                for metric, value in values.items()
                if value is not None
            }
        )
        mlflow.log_metrics(
            {
                key: result["uncertainty"][key]
                for key in ("ci_low", "ci_high", "mae_improvement_a_minus_b")
            }
        )
        mlflow.log_input(
            mlflow.data.from_pandas(
                frame[columns], targets="target_departures", name="p1_septiembre_comun"
            ),
            context="evaluation",
        )
        plot_comparison(result, output_dir / "comparacion.png")
        write_json(output_dir / "resultados.json", result)
        (output_dir / "resultados.md").write_text(markdown_result(result), encoding="utf-8")
        for artifact in output_dir.iterdir():
            if artifact.name in ("resultados.json", "resultados.md", "comparacion.png"):
                mlflow.log_artifact(str(artifact), artifact_path="comparacion")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="A/B offline de P1 desde el Model Registry")
    parser.add_argument("--tracking-uri")
    parser.add_argument("--model-name", default=REGISTERED_MODELS["P1"])
    parser.add_argument("--champion-version", type=int)
    parser.add_argument("--challenger-version", type=int)
    parser.add_argument("--data-dir", type=Path, default=cfg.DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=cfg.SEED)
    parser.add_argument("--bootstrap-repeats", type=int, default=BOOTSTRAP_REPEATS)
    parser.add_argument("--block-days", type=int, default=BLOCK_DAYS)
    args = parser.parse_args(argv)
    if any(
        value is not None and value < 1
        for value in (args.champion_version, args.challenger_version)
    ):
        parser.error("Las versiones deben ser enteros positivos")
    try:
        verify_data(args.data_dir)
        configure_mlflow(tracking_uri=args.tracking_uri)
        result = compare_registered(
            args.model_name,
            args.data_dir,
            args.output_dir,
            args.champion_version,
            args.challenger_version,
            args.seed,
            args.bootstrap_repeats,
            args.block_days,
        )
    except (ValueError, MlflowException, OSError) as error:
        parser.exit(1, f"Comparación no completada: {error}\n")
    print(
        json.dumps(
            {
                "run_id": result["run_id"],
                "metrics": result["metrics"],
                "decision": result["decision"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
