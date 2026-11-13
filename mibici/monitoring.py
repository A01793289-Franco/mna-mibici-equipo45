"""Monitoreo de data drift y calidad de datos con Evidently.

Uso desde la raíz del repositorio (después de ``python -m mibici.features``)::

    python -m pip install -r requirements-validation.txt
    python -m mibici.monitoring
    python -m mibici.monitoring --current jul_ago --dataset p1

Compara un conjunto de **referencia** con un conjunto **actual** y escribe, por tabla de
variables (P1 y P2), un reporte HTML de Evidently con el drift por variable y la calidad de los
datos, más ``resumen.json`` y ``resumen.md`` con lo esencial (evidencia versionada).

- **Referencia:** el periodo de entrenamiento, 2026-01-08 a 2026-06-30. Es la distribución con la
  que se ajustaron los modelos.
- **Actual:** un periodo posterior que hace de producción. Por defecto septiembre de 2026 (el mes
  más reciente de los datos abiertos); con ``--current jul_ago`` se usa julio-agosto, el periodo de
  validación, para ver si el cambio es gradual. No hay un año posterior en los datos abiertos
  usados y la API no registra las peticiones que recibe, así que septiembre simula producción.

Solo se comparan las variables de entrada, no el objetivo ni las predicciones, de modo que
ningún modelo se evalúa y no se consume el uso único del conjunto de prueba. ``month`` se excluye
porque cada periodo cubre meses distintos y siempre mostraría drift. Se usan todas las filas,
sin muestreo, y los umbrales por defecto de Evidently: distancia de Wasserstein normalizada 0.1
para variables numéricas y distancia de Jensen-Shannon 0.1 para categóricas; el conjunto se
considera con drift si la mitad o más de las columnas lo muestran.
"""

import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path

import pandas as pd

from mibici import config as cfg
from mibici.dataset import write_json

OUTPUT_DIR = cfg.ROOT_DIR / "reports" / "evidently"
REFERENCE_SPLIT = "train"
CURRENT_PERIODS = {
    "sep": {"split": "test", "etiqueta": "septiembre 2026"},
    "jul_ago": {"split": "val", "etiqueta": "julio-agosto 2026"},
}
DEFAULT_CURRENT = "sep"
EXCLUDED = ("month",)
KEY = ["station_id", "timestamp"]
SPECS = {"p1": cfg.P1_FEATURE_COLUMNS, "p2": cfg.P2_FEATURE_COLUMNS}
CATEGORICAL = ("station_id", *(c for c in cfg.CALENDAR_FEATURES if c not in EXCLUDED))
DRIFT_SHARE = 0.5


def columns(name):
    """Variables del conjunto que se comparan: la estación y las del modelo, sin ``month``."""
    return ["station_id", *(c for c in SPECS[name] if c not in EXCLUDED)]


def load_table(name, data_dir=cfg.DATA_DIR):
    """Tabla de variables de ``data/processed`` con su columna ``split``."""
    return pd.read_parquet(cfg.data_path(cfg.FEATURE_FILES[name], data_dir))


def split_sets(table, current=DEFAULT_CURRENT):
    """Regresa ``(referencia, actual)`` según la partición temporal del proyecto."""
    period = CURRENT_PERIODS[current]
    return (
        table[table["split"] == REFERENCE_SPLIT].reset_index(drop=True),
        table[table["split"] == period["split"]].reset_index(drop=True),
    )


def prepare(frame, name):
    """Deja solo las columnas comparadas, con las categóricas como texto y fechas sin zona.

    Evidently no acepta etiquetas enteras de NumPy en las variables categóricas.
    """
    result = frame[["timestamp", *columns(name)]].copy()
    result["timestamp"] = result["timestamp"].dt.tz_localize(None)
    for column in CATEGORICAL:
        if column in result:
            result[column] = result[column].astype(str)
    return result


def evidently_report(reference, current, name):
    """Ejecuta ``DataDriftPreset`` y ``DataSummaryPreset``; regresa la instantánea."""
    from evidently import DataDefinition, Dataset, Report
    from evidently.presets import DataDriftPreset, DataSummaryPreset

    names = columns(name)
    definition = DataDefinition(
        numerical_columns=[c for c in names if c not in CATEGORICAL],
        categorical_columns=[c for c in names if c in CATEGORICAL],
        datetime_columns=["timestamp"],
    )
    report = Report([DataDriftPreset(drift_share=DRIFT_SHARE), DataSummaryPreset()])
    return report.run(
        Dataset.from_pandas(current, data_definition=definition),
        Dataset.from_pandas(reference, data_definition=definition),
    )


def is_drifted(method, score, threshold):
    """Regla de Evidently: en pruebas de p-valor hay drift si es menor al umbral; en distancias,
    si es mayor o igual."""
    return score < threshold if "p_value" in method.lower() else score >= threshold


def drift_from_snapshot(result, reference, current):
    """Drift por variable y del conjunto a partir de ``snapshot.dict()``.

    La regla de drift depende de la prueba (ver ``is_drifted``). Se añade la media de
    cada variable numérica en ambos periodos para ver el sentido del cambio.
    """
    rows, share = [], None
    for metric in result["metrics"]:
        config = metric["config"]
        kind = config["type"].rsplit(":", 1)[-1]
        if kind == "DriftedColumnsCount":
            share = float(metric["value"]["share"])
        elif kind == "ValueDrift":
            column = config["column"]
            score, threshold = float(metric["value"]), float(config["threshold"])
            row = {
                "variable": column,
                "tipo": "categórica" if column in CATEGORICAL else "numérica",
                "prueba": config["method"],
                "umbral": threshold,
                "distancia": score,
                "deriva": is_drifted(config["method"], score, threshold),
            }
            if column not in CATEGORICAL:
                row["media_referencia"] = float(reference[column].mean())
                row["media_actual"] = float(current[column].mean())
            rows.append(row)
    if share is None:
        raise ValueError("El reporte no contiene DriftedColumnsCount")
    drifted = [row["variable"] for row in rows if row["deriva"]]
    return {
        "variables": rows,
        "variables_con_deriva": drifted,
        "proporcion_con_deriva": share,
        "deriva_del_conjunto": share >= DRIFT_SHARE,
    }


def quality(frame, name):
    """Calidad básica de un periodo: faltantes, duplicados, constantes y estaciones."""
    names = columns(name)
    return {
        "filas": int(len(frame)),
        "inicio": frame["timestamp"].min().isoformat(),
        "fin": frame["timestamp"].max().isoformat(),
        "estaciones": int(frame["station_id"].nunique()),
        "valores_faltantes": int(frame[names].isna().sum().sum()),
        "filas_duplicadas": int(frame.duplicated(subset=KEY).sum()),
        "columnas_constantes": [c for c in names if frame[c].nunique(dropna=False) <= 1],
    }


def new_stations(reference, current):
    """Estaciones del periodo actual que no aparecen en la referencia y su peso en las filas."""
    unseen = ~current["station_id"].isin(set(reference["station_id"]))
    return {
        "estaciones_nuevas": int(current.loc[unseen, "station_id"].nunique()),
        "proporcion_de_filas": float(unseen.mean()),
    }


def compare(name, table, current=DEFAULT_CURRENT):
    """Compara referencia y periodo actual de una tabla; regresa ``(resumen, instantánea)``."""
    reference, now = split_sets(table, current)
    if reference.empty or now.empty:
        raise ValueError(f"La tabla {name} no tiene filas para {REFERENCE_SPLIT} y {current}")
    ref_prepared, now_prepared = prepare(reference, name), prepare(now, name)
    snapshot = evidently_report(ref_prepared, now_prepared, name)
    summary = {
        "conjunto": name,
        "actual": current,
        "etiqueta_actual": CURRENT_PERIODS[current]["etiqueta"],
        **drift_from_snapshot(snapshot.dict(), reference, now),
        "calidad": {"referencia": quality(reference, name), "actual": quality(now, name)},
        "estaciones": new_stations(reference, now),
    }
    return summary, snapshot


def manifest_value(path, key):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))[key]
    except (OSError, KeyError, ValueError):
        return "no disponible"


def markdown_summary(summary):
    """Tablas legibles del resumen para revisar la evidencia sin abrir el JSON ni el HTML."""
    lines = [
        "# Drift y calidad de datos con Evidently",
        "",
        f"- Generado: {summary['generado']}",
        f"- evidently {summary['evidently']}, todas las filas, sin muestreo",
        f"- data_version `{summary['data_version'][:12]}`, "
        f"feature_version `{summary['feature_version'][:12]}`",
        "",
        summary["nota"],
    ]
    for item in summary["comparaciones"]:
        ref, now = item["calidad"]["referencia"], item["calidad"]["actual"]
        lines += [
            "",
            f"## {item['conjunto'].upper()}: entrenamiento contra {item['etiqueta_actual']}",
            "",
            f"- Referencia: {ref['inicio'][:10]} a {ref['fin'][:10]}, {ref['filas']:,} filas.",
            f"- Actual: {now['inicio'][:10]} a {now['fin'][:10]}, {now['filas']:,} filas.",
            f"- Variables con drift: {len(item['variables_con_deriva'])} de "
            f"{len(item['variables'])} ({item['proporcion_con_deriva']:.0%}); "
            f"conjunto con drift: **{'sí' if item['deriva_del_conjunto'] else 'no'}**.",
            "",
            "| Variable | Tipo | Prueba | Distancia | Umbral | Drift | Media ref. | Media actual |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for row in item["variables"]:
            means = (
                f"{row['media_referencia']:.3f} | {row['media_actual']:.3f}"
                if "media_referencia" in row
                else "- | -"
            )
            lines.append(
                f"| {row['variable']} | {row['tipo']} | {row['prueba']} | "
                f"{row['distancia']:.4f} | {row['umbral']:.2f} | "
                f"{'sí' if row['deriva'] else 'no'} | {means} |"
            )
        stations = item["estaciones"]
        lines += [
            "",
            f"Estaciones del periodo actual ausentes de la referencia: "
            f"{stations['estaciones_nuevas']}, con {stations['proporcion_de_filas']:.1%} de sus filas.",
            "",
            "| Calidad | Referencia | Actual |",
            "|---|---|---|",
        ]
        for label, key in (
            ("Filas", "filas"),
            ("Estaciones", "estaciones"),
            ("Valores faltantes", "valores_faltantes"),
            ("Filas duplicadas (estación y hora)", "filas_duplicadas"),
        ):
            lines.append(f"| {label} | {ref[key]:,} | {now[key]:,} |")
        constants = ", ".join(now["columnas_constantes"] or ["ninguna"])
        lines.append(
            f"| Columnas constantes | {', '.join(ref['columnas_constantes']) or 'ninguna'} | {constants} |"
        )
    return "\n".join(lines) + "\n"


def monitor(
    names=tuple(SPECS),
    currents=(DEFAULT_CURRENT,),
    data_dir=cfg.DATA_DIR,
    output_dir=OUTPUT_DIR,
    html=True,
):
    """Genera los reportes pedidos, escribe el resumen y regresa el diccionario del resumen."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    comparisons = []
    for name in names:
        table = load_table(name, data_dir)
        for current in currents:
            print(f"Comparando {name} con {current}...", flush=True)
            item, snapshot = compare(name, table, current)
            comparisons.append(item)
            if html:
                snapshot.save_html(str(output_dir / f"{name}_{current}.html"))
    summary = {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evidently": version("evidently"),
        "data_version": manifest_value(cfg.MANIFEST_PATH, "data_version"),
        "feature_version": manifest_value(cfg.FEATURE_MANIFEST_PATH, "feature_version"),
        "nota": (
            "Referencia: periodo de entrenamiento. Actual: periodo posterior que simula "
            "producción. Solo se comparan variables de entrada; no se evalúa ningún modelo ni "
            "se usa el conjunto de prueba para decidir. month se excluye porque cada periodo "
            "cubre meses distintos. Umbrales por defecto de Evidently: 0.1 en la distancia "
            "de Wasserstein normalizada (numéricas) y de Jensen-Shannon (categóricas)."
        ),
        "comparaciones": comparisons,
    }
    write_json(output_dir / "resumen.json", summary)
    (output_dir / "resumen.md").write_text(
        markdown_summary(summary), encoding="utf-8", newline="\n"
    )
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description="Drift y calidad de datos con Evidently.")
    parser.add_argument("--dataset", nargs="+", choices=list(SPECS), default=list(SPECS))
    parser.add_argument(
        "--current",
        nargs="+",
        choices=list(CURRENT_PERIODS),
        default=[DEFAULT_CURRENT],
        help="Periodo actual: sep (septiembre) o jul_ago (julio-agosto)",
    )
    parser.add_argument("--data-dir", type=Path, default=cfg.DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--no-html", action="store_true", help="Solo escribir el resumen")
    args = parser.parse_args(argv)
    summary = monitor(
        args.dataset, args.current, args.data_dir, args.output_dir, html=not args.no_html
    )
    for item in summary["comparaciones"]:
        drifted = ", ".join(item["variables_con_deriva"]) or "ninguna"
        print(f"{item['conjunto']} contra {item['actual']}: drift en {drifted}")
    print(f"Resumen en {args.output_dir / 'resumen.md'}")


if __name__ == "__main__":
    main()
