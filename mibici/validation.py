"""Validación de datos de P1-P3 con DeepChecks: integridad, partición temporal y drift.

Uso desde la raíz del repositorio (después de ``python -m mibici.features``)::

    python -m pip install -r requirements-validation.txt
    python -m mibici.validation
    python -m mibici.validation --dataset p1 --html

Lee las tablas de ``data/processed`` y ejecuta tres suites por conjunto:

- **integridad** (bloqueante): tipos esperados, nulos, duplicados (filas y llave estación-hora),
  columnas constantes y reglas de rango y coherencia propias del proyecto.
- **partición** (bloqueante): entrenamiento contra validación y contra prueba sin fechas solapadas
  ni clases nuevas de P2.
- **drift** (informativa): cambio de distribución de variables y objetivo. Se reporta pero no
  detiene el proceso: hay estacionalidad esperada entre enero-junio, julio-agosto y septiembre.

Comparar distribuciones de septiembre no evalúa ningún modelo, así que no consume el uso único
del conjunto de prueba que fija el protocolo. Escribe ``reports/deepchecks/resumen.json`` y
``resumen.md`` (evidencia versionada). Con ``--html`` escribe además un reporte por suite en
``reports/deepchecks/html``, fuera de Git por tamaño (los de drift superan 40 MB). Termina con
código 1 si falla alguna suite bloqueante.
"""

import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from mibici import config as cfg
from mibici.dataset import write_json
from mibici.features import temporal_split

OUTPUT_DIR = cfg.ROOT_DIR / "reports" / "deepchecks"
DRIFT_SAMPLE_ROWS = 100_000
ALL_ROWS = 10**9
HOURLY_KEY = ["station_id", "timestamp"]
# Área metropolitana de Guadalajara, holgada: detecta coordenadas invertidas o en cero.
LATITUDE_RANGE = (20.4, 21.0)
LONGITUDE_RANGE = (-103.7, -103.1)


def apply_compat():
    """Adapta el entorno a deepchecks 0.19.1, publicado antes de numpy 2, pandas 3 y sklearn 1.9.

    Solo añade nombres que esas versiones eliminaron, sin cambiar los existentes:
    ``np.Inf``, ``DataFrame.applymap`` y el scorer ``max_error``. También desactiva el aviso
    de versión de deepchecks, que al importarse envía un identificador anónimo a su servidor.
    Debe ejecutarse antes de importar deepchecks.
    """
    from sklearn.metrics import _scorer, make_scorer, max_error

    os.environ.setdefault("DISABLE_DEEPCHECKS_ANONYMOUS_TELEMETRY", "True")
    if "Inf" not in np.__dict__:
        np.Inf = np.inf
    if not hasattr(pd.DataFrame, "applymap"):
        pd.DataFrame.applymap = pd.DataFrame.map
    _scorer._SCORERS.setdefault("max_error", make_scorer(max_error, greater_is_better=False))


apply_compat()

from deepchecks.core import (  # noqa: E402
    CheckResult,
    ConditionCategory,
    ConditionResult,
)
from deepchecks.core.check_result import CheckFailure  # noqa: E402
from deepchecks.tabular import Dataset, SingleDatasetCheck, Suite  # noqa: E402
from deepchecks.tabular.checks import (  # noqa: E402
    DataDuplicates,
    DateTrainTestLeakageOverlap,
    FeatureDrift,
    IsSingleValue,
    LabelDrift,
    MixedDataTypes,
    MixedNulls,
    NewLabelTrainTest,
    PercentOfNulls,
)


# ---------------------------------------------------------------------------
# Checks propios: esquema y reglas de dominio
# ---------------------------------------------------------------------------
class ExpectedDtypes(SingleDatasetCheck):
    """Compara columnas y tipos con el esquema que producen ``features.py`` y ``train.py``."""

    def __init__(self, schema, **kwargs):
        super().__init__(**kwargs)
        self.schema = schema

    def run_logic(self, context, dataset_kind) -> CheckResult:
        data = context.get_data_by_kind(dataset_kind).data
        rows = [
            {
                "columna": column,
                "esperado": expected,
                "observado": str(data[column].dtype) if column in data else "ausente",
            }
            for column, expected in self.schema.items()
        ]
        rows += [
            {"columna": column, "esperado": "no declarada", "observado": str(data[column].dtype)}
            for column in data.columns
            if column not in self.schema
        ]
        table = pd.DataFrame(rows)
        mismatches = table[table.esperado != table.observado]
        value = dict(zip(mismatches.columna, mismatches.observado))
        return CheckResult(value, header="Tipos de datos esperados", display=[table])

    def add_condition_schema_matches(self):
        def condition(value):
            if not value:
                return ConditionResult(ConditionCategory.PASS, "Columnas y tipos coinciden")
            return ConditionResult(ConditionCategory.FAIL, f"Diferencias: {value}")

        return self.add_condition("Columnas y tipos coinciden con el esquema", condition)


class ValueRules(SingleDatasetCheck):
    """Cuenta filas que violan reglas de rango o coherencia del dominio de MiBici."""

    def __init__(self, rules, **kwargs):
        super().__init__(**kwargs)
        self.rules = rules

    def run_logic(self, context, dataset_kind) -> CheckResult:
        data = context.get_data_by_kind(dataset_kind).data
        value = {name: int(rule(data).sum()) for name, rule in self.rules.items()}
        table = pd.DataFrame({"regla": list(value), "filas_invalidas": list(value.values())})
        return CheckResult(value, header="Rangos y coherencia del dominio", display=[table])

    def add_condition_no_violations(self):
        def condition(value):
            failed = {name: count for name, count in value.items() if count}
            if not failed:
                return ConditionResult(
                    ConditionCategory.PASS, f"{len(value)} reglas sin filas inválidas"
                )
            return ConditionResult(ConditionCategory.FAIL, f"Filas inválidas: {failed}")

        return self.add_condition("Ninguna fila viola las reglas", condition)


# ---------------------------------------------------------------------------
# Esquemas y reglas por conjunto
# ---------------------------------------------------------------------------
def outside(series, low, high):
    return ~series.between(low, high)


def hourly_rules(target):
    """Reglas comunes a P1 y P2: calendario, conteos, periodo y partición."""
    counts = [c for c in cfg.P1_FEATURE_COLUMNS if c.startswith("departures_")]
    return {
        "station_id positivo": lambda d: d.station_id <= 0,
        "hour en 0-23 e igual a la hora de timestamp": lambda d: outside(d.hour, 0, 23)
        | (d.hour != d.timestamp.dt.hour),
        "weekday en 0-6 e igual al día de timestamp": lambda d: outside(d.weekday, 0, 6)
        | (d.weekday != d.timestamp.dt.dayofweek),
        "is_weekend coherente con weekday": lambda d: d.is_weekend
        != (d.weekday >= 5).astype("int8"),
        "month igual al mes de timestamp": lambda d: d.month != d.timestamp.dt.month,
        "rezagos, medias y objetivo no negativos": lambda d: (d[[*counts, target]] < 0).any(
            axis=1
        ),
        "timestamp dentro del periodo": lambda d: (
            d.timestamp < pd.Timestamp(cfg.START_DATE, tz=cfg.TIMEZONE)
        )
        | (d.timestamp >= pd.Timestamp(cfg.END_DATE_EXCLUSIVE, tz=cfg.TIMEZONE)),
        "split coincide con los cortes de config.py": lambda d: d.split.ne(
            temporal_split(d.timestamp)
        )
        .fillna(True)
        .to_numpy(),
    }


def hourly_schema(feature_columns, target, target_dtype):
    schema = {
        "station_id": "int32",
        "timestamp": f"datetime64[us, {cfg.TIMEZONE}]",
        "split": "string",
    }
    for column in feature_columns:
        schema[column] = "int8" if column in cfg.CALENDAR_FEATURES else "float64"
    schema[target] = target_dtype
    return schema


P2_EXTRA_RULES = {
    "virtual_occupancy en [0, 1]": lambda d: outside(d.virtual_occupancy, 0, 1),
    "target_risk en {0, 1, 2}": lambda d: ~d.target_risk.isin([0, 1, 2]),
    "flujos netos enteros": lambda d: (d[["net_flow_lag_1", "net_flow_lag_24"]] % 1 != 0).any(
        axis=1
    ),
}
P3_RULES = {
    "perfiles en [0, 1]": lambda d: (
        (d[list(cfg.P3_FEATURE_COLUMNS)] < 0) | (d[list(cfg.P3_FEATURE_COLUMNS)] > 1)
    ).any(axis=1),
    "perfil normalizado (suma 1)": lambda d: ~np.isclose(
        d[list(cfg.P3_FEATURE_COLUMNS)].sum(axis=1), 1
    ),
    f"observed_days >= {cfg.MIN_PROFILE_DAYS}": lambda d: d.observed_days < cfg.MIN_PROFILE_DAYS,
    "latitud en Guadalajara": lambda d: outside(d.latitude, *LATITUDE_RANGE).fillna(True),
    "longitud en Guadalajara": lambda d: outside(d.longitude, *LONGITUDE_RANGE).fillna(True),
}
P3_SCHEMA = {
    "station_id": "int32",
    **{column: "float64" for column in cfg.P3_FEATURE_COLUMNS},
    "observed_days": "int64",
    "name": "string",
    "latitude": "Float64",
    "longitude": "Float64",
}

# Cada conjunto: esquema, reglas, variables, objetivo, llave de duplicados y columnas que pueden
# ser constantes. ``month`` se excluye del drift: cada partición cubre meses distintos por diseño.
SPECS = {
    "p1": {
        "schema": hourly_schema(cfg.P1_FEATURE_COLUMNS, "target_departures", "int32"),
        "rules": hourly_rules("target_departures"),
        "features": list(cfg.P1_FEATURE_COLUMNS),
        "label": "target_departures",
        "key": HOURLY_KEY,
        "constant_allowed": ["split"],
    },
    "p2": {
        "schema": hourly_schema(cfg.P2_FEATURE_COLUMNS, "target_risk", "int8"),
        "rules": {**hourly_rules("target_risk"), **P2_EXTRA_RULES},
        "features": list(cfg.P2_FEATURE_COLUMNS),
        "label": "target_risk",
        "key": HOURLY_KEY,
        "constant_allowed": ["split"],
    },
    "p3": {
        "schema": P3_SCHEMA,
        "rules": P3_RULES,
        "features": list(cfg.P3_FEATURE_COLUMNS),
        "label": None,
        "key": ["station_id"],
        # De madrugada el servicio no opera: esas horas valen 0 en todas las estaciones.
        "constant_allowed": list(cfg.P3_FEATURE_COLUMNS),
    },
}
DRIFT_EXCLUDED = ["month"]


# ---------------------------------------------------------------------------
# Datasets y suites
# ---------------------------------------------------------------------------
def load_tables(name, data_dir=cfg.DATA_DIR):
    """Regresa ``{"train", "val", "test"}`` para un conjunto, leído de ``data/processed``."""
    if name == "p3":
        return {
            split: pd.read_parquet(cfg.data_path(cfg.FEATURE_FILES[f"p3_{split}"], data_dir))
            for split in ("train", "val", "test")
        }
    table = pd.read_parquet(cfg.data_path(cfg.FEATURE_FILES[name], data_dir))
    return {split: table[table.split == split] for split in ("train", "val", "test")}


def make_dataset(frame, spec, features=None, with_datetime=False):
    """Envuelve una tabla en un ``Dataset`` de deepchecks sin copiar ni convertir columnas."""
    categorical = [c for c in cfg.CALENDAR_FEATURES if c in (features or spec["features"])]
    options = {
        "label": spec["label"],
        "features": features or spec["features"],
        "cat_features": categorical,
    }
    if with_datetime:
        frame = frame.assign(timestamp=frame.timestamp.dt.tz_localize(None))
        options["datetime_name"] = "timestamp"
    return Dataset(frame, **options)


def integrity_suite(spec):
    key = spec["key"]
    checks = [
        ExpectedDtypes(spec["schema"]).add_condition_schema_matches(),
        MixedDataTypes().add_condition_rare_type_ratio_not_in_range(),
        PercentOfNulls(n_samples=ALL_ROWS).add_condition_percent_of_nulls_not_greater_than(0),
        MixedNulls(n_samples=ALL_ROWS).add_condition_different_nulls_less_equal_to(),
        DataDuplicates(n_samples=ALL_ROWS).add_condition_ratio_less_or_equal(0),
        DataDuplicates(columns=key, n_samples=ALL_ROWS).add_condition_ratio_less_or_equal(0),
        IsSingleValue(ignore_columns=spec["constant_allowed"]).add_condition_not_single_value(),
        ValueRules(spec["rules"]).add_condition_no_violations(),
    ]
    return Suite("integridad", *checks)


def partition_suite(spec):
    checks = []
    if "timestamp" in spec["key"]:
        checks.append(DateTrainTestLeakageOverlap().add_condition_leakage_ratio_less_or_equal(0))
    if spec["label"] == "target_risk":
        checks.append(NewLabelTrainTest().add_condition_new_labels_number_less_or_equal(0))
    return Suite("particion", *checks) if checks else None


def drift_suite(spec, sample_rows=DRIFT_SAMPLE_ROWS):
    checks = [
        FeatureDrift(
            n_samples=sample_rows, random_state=cfg.SEED, n_top_columns=len(spec["features"])
        ).add_condition_drift_score_less_than()
    ]
    if spec["label"]:
        checks.append(
            LabelDrift(
                n_samples=sample_rows, random_state=cfg.SEED
            ).add_condition_drift_score_less_than()
        )
    return Suite("drift", *checks)


# ---------------------------------------------------------------------------
# Resumen
# ---------------------------------------------------------------------------
def summarize(result, suite, comparison, blocking):
    """Convierte un ``SuiteResult`` en registros JSON con el estado de cada condición."""
    checks = []
    for item in result.results:
        name = type(item.check).__name__
        if isinstance(item, CheckFailure):
            checks.append({"check": name, "estado": "error", "detalle": str(item.exception)})
            continue
        conditions = [
            {
                "condicion": condition.name,
                "resultado": condition.category.value,
                "detalle": condition.details,
            }
            for condition in item.conditions_results
        ]
        record = {
            "check": name,
            "titulo": item.get_header(),
            "estado": (
                "aprobado" if all(c.is_pass() for c in item.conditions_results) else "fallido"
            ),
            "condiciones": conditions,
        }
        if name == "FeatureDrift":
            record["drift_por_variable"] = {
                column: round(float(scores["Drift score"]), 4)
                for column, scores in item.value.items()
            }
        if name == "LabelDrift":
            record["drift_objetivo"] = round(float(item.value["Drift score"]), 4)
        checks.append(record)
    passed = all(check["estado"] == "aprobado" for check in checks)
    return {
        "suite": suite,
        "comparacion": comparison,
        "bloqueante": blocking,
        "aprobada": passed,
        "checks": checks,
    }


def run_suite(suite, datasets, html_dir, label):
    result = suite.run(*datasets)
    if html_dir is not None:
        html_dir.mkdir(parents=True, exist_ok=True)
        result.save_as_html(str(html_dir / f"{label}.html"), as_widget=False, connected=True)
    return result


def validate_dataset(name, tables, html_dir=None, sample_rows=DRIFT_SAMPLE_ROWS):
    """Ejecuta las tres suites para un conjunto y regresa su resumen."""
    spec = SPECS[name]
    drift_features = [c for c in spec["features"] if c not in DRIFT_EXCLUDED]
    with_datetime = "timestamp" in spec["key"]
    suites = []
    full = pd.concat(tables.values(), ignore_index=True) if name != "p3" else None
    targets = {"completo": full} if full is not None else {f"p3_{s}": t for s, t in tables.items()}
    for label, frame in targets.items():
        dataset = make_dataset(frame, spec)
        result = run_suite(
            integrity_suite(spec), [dataset], html_dir, f"{name}_integridad_{label}"
        )
        suites.append(summarize(result, "integridad", label, True))
    partition = partition_suite(spec)
    for other in ("val", "test"):
        comparison = f"train-{other}"
        if partition is not None:
            pair = [make_dataset(tables[s], spec, with_datetime=True) for s in ("train", other)]
            result = run_suite(partition, pair, html_dir, f"{name}_particion_{comparison}")
            suites.append(summarize(result, "particion", comparison, True))
        pair = [
            make_dataset(tables[s], spec, drift_features, with_datetime) for s in ("train", other)
        ]
        result = run_suite(
            drift_suite(spec, sample_rows), pair, html_dir, f"{name}_drift_{comparison}"
        )
        suites.append(summarize(result, "drift", comparison, False))
    return {
        "filas": {split: int(len(frame)) for split, frame in tables.items()},
        "aprobado": all(s["aprobada"] for s in suites if s["bloqueante"]),
        "suites": suites,
    }


def manifest_value(path, key):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))[key]
    except (OSError, KeyError, ValueError):
        return "no disponible"


def markdown_summary(summary):
    """Tabla legible del resumen para revisar la evidencia sin abrir el JSON."""
    lines = [
        "# Validación de datos con DeepChecks",
        "",
        f"- Generado: {summary['generado']}",
        f"- deepchecks {summary['deepchecks']}, semilla {summary['semilla']}, "
        f"muestra de drift {summary['muestra_drift']:,} filas por conjunto",
        f"- data_version `{summary['data_version'][:12]}`, "
        f"feature_version `{summary['feature_version'][:12]}`",
        f"- Resultado de suites bloqueantes: **{'aprobado' if summary['aprobado'] else 'fallido'}**",
        "",
        summary["nota"],
        "",
        "| Conjunto | Suite | Comparación | Bloqueante | Check | Estado | Detalle |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, dataset in summary["conjuntos"].items():
        for suite in dataset["suites"]:
            for check in suite["checks"]:
                details = "; ".join(c["detalle"] for c in check.get("condiciones", []))
                details = (
                    (details or check.get("detalle", "")).replace("|", "/").replace("\n", " ")
                )
                lines.append(
                    f"| {name} | {suite['suite']} | {suite['comparacion']} | "
                    f"{'sí' if suite['bloqueante'] else 'no'} | {check['check']} | "
                    f"{check['estado']} | {details[:300]} |"
                )
    return "\n".join(lines) + "\n"


def validate(
    names=tuple(SPECS),
    data_dir=cfg.DATA_DIR,
    output_dir=OUTPUT_DIR,
    html=False,
    sample_rows=DRIFT_SAMPLE_ROWS,
):
    """Valida los conjuntos pedidos, escribe el resumen y regresa ``(aprobado, resumen)``."""
    output_dir = Path(output_dir)
    html_dir = output_dir / "html" if html else None
    results = {}
    for name in names:
        print(f"Validando {name}...")
        results[name] = validate_dataset(name, load_tables(name, data_dir), html_dir, sample_rows)
    summary = {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "deepchecks": version("deepchecks"),
        "semilla": cfg.SEED,
        "muestra_drift": sample_rows,
        "data_version": manifest_value(cfg.MANIFEST_PATH, "data_version"),
        "feature_version": manifest_value(cfg.FEATURE_MANIFEST_PATH, "feature_version"),
        "nota": (
            "Las suites de integridad y partición son bloqueantes. El drift es informativo: "
            "enero-junio, julio-agosto y septiembre tienen estacionalidad esperada, y month se "
            "excluye porque cada partición cubre meses distintos. Comparar distribuciones de "
            "septiembre no evalúa modelos ni consume el uso único del conjunto de prueba. "
            "MultivariateDrift no se usa: es incompatible con scikit-learn 1.9."
        ),
        "aprobado": all(result["aprobado"] for result in results.values()),
        "conjuntos": results,
    }
    write_json(output_dir / "resumen.json", summary)
    (output_dir / "resumen.md").write_text(
        markdown_summary(summary), encoding="utf-8", newline="\n"
    )
    return summary["aprobado"], summary


def main(argv=None):
    parser = argparse.ArgumentParser(description="Valida las tablas de P1-P3 con DeepChecks.")
    parser.add_argument(
        "--dataset",
        nargs="+",
        choices=list(SPECS),
        default=list(SPECS),
        help="Conjuntos a validar",
    )
    parser.add_argument("--data-dir", type=Path, default=cfg.DATA_DIR, help="Carpeta de datos")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR, help="Carpeta del reporte")
    parser.add_argument(
        "--sample-rows",
        type=int,
        default=DRIFT_SAMPLE_ROWS,
        help="Filas muestreadas con la semilla del proyecto para el drift",
    )
    parser.add_argument(
        "--html", action="store_true", help="Escribir un reporte HTML por suite (pesados)"
    )
    args = parser.parse_args(argv)
    passed, summary = validate(
        args.dataset, args.data_dir, args.output_dir, args.html, args.sample_rows
    )
    for name, result in summary["conjuntos"].items():
        failed = [
            f"{s['suite']} {s['comparacion']}: {c['check']}"
            for s in result["suites"]
            for c in s["checks"]
            if c["estado"] != "aprobado"
        ]
        state = "aprobado" if result["aprobado"] else "FALLIDO"
        print(f"{name}: {state}" + (f" (no aprobados: {', '.join(failed)})" if failed else ""))
    print(f"Resumen en {Path(args.output_dir) / 'resumen.md'}")
    if not passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
