"""Ejecuta los escenarios de carga con Locust y resume latencia, RPS y tasa de error.

Uso (con la API de Compose levantada en el puerto 8000)::

    python -m mibici.load_test
    python -m mibici.load_test --scenario carga --seconds 30

Genera en ``reports/carga/``: ``resumen.json``, ``resumen.md`` y un HTML de Locust por
escenario. Los CSV crudos de Locust se guardan junto a ellos, pero Git los ignora.
"""

import argparse
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import subprocess
import sys

import requests

LOCUSTFILE = Path("load") / "locustfile.py"
OUTPUT = Path("reports") / "carga"

# Usuarios simultáneos, usuarios nuevos por segundo y duración en segundos.
SCENARIOS = {
    "baseline": {"users": 5, "spawn_rate": 1, "seconds": 60},
    "carga": {"users": 25, "spawn_rate": 5, "seconds": 120},
    "estres": {"users": 100, "spawn_rate": 20, "seconds": 120},
}
LIMITS = {"p95_ms": 500.0, "error_rate_pct": 1.0}


class LoadTestError(RuntimeError):
    pass


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def read_rows(path):
    """Filas de un CSV de Locust; en Windows puede venir en cp1252 en lugar de UTF-8."""
    data = Path(path).read_bytes()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252")
    return list(csv.DictReader(io.StringIO(text, newline="")))


def parse_stats(path):
    """Lee ``*_stats.csv`` de Locust y devuelve las métricas por endpoint y el agregado."""
    endpoints = {}
    for row in read_rows(path):
        requests_total = int(number(row["Request Count"]))
        failures = int(number(row["Failure Count"]))
        endpoints[row["Name"]] = {
            "requests": requests_total,
            "failures": failures,
            "error_rate_pct": (
                round(100 * failures / requests_total, 3) if requests_total else 0.0
            ),
            "rps": round(number(row["Requests/s"]), 2),
            "mean_ms": round(number(row["Average Response Time"]), 1),
            "p50_ms": round(number(row["50%"]), 1),
            "p95_ms": round(number(row["95%"]), 1),
            "p99_ms": round(number(row["99%"]), 1),
            "max_ms": round(number(row["Max Response Time"]), 1),
        }
    if "Aggregated" not in endpoints:
        raise LoadTestError(f"{path} no contiene la fila Aggregated")
    return endpoints


def parse_failures(path):
    path = Path(path)
    if not path.exists():
        return []
    return [
        {
            "endpoint": row["Name"],
            "error": row["Error"],
            "occurrences": int(number(row["Occurrences"])),
        }
        for row in read_rows(path)
    ]


def evaluate(aggregated, limits=None):
    limits = limits or LIMITS
    checks = {
        "p95_ms": aggregated["p95_ms"] <= limits["p95_ms"],
        "error_rate_pct": aggregated["error_rate_pct"] <= limits["error_rate_pct"],
    }
    return {"limits": limits, "checks": checks, "passed": all(checks.values())}


def summarize_scenario(name, scenario, directory, limits=None):
    directory = Path(directory)
    endpoints = parse_stats(directory / f"{name}_stats.csv")
    aggregated = endpoints.pop("Aggregated")
    return {
        "scenario": scenario,
        "aggregated": aggregated,
        "endpoints": endpoints,
        "failures": parse_failures(directory / f"{name}_failures.csv"),
        "evaluation": evaluate(aggregated, limits),
    }


def render_markdown(summary):
    lines = [
        "# Pruebas de carga con Locust",
        "",
        f"**Host:** `{summary['host']}` · **Fecha (UTC):** {summary['generated_at']} · "
        f"**Locust:** {summary['locust']}",
        "",
        "## Resumen por escenario",
        "",
        "| Escenario | Usuarios | Duración (s) | Peticiones | RPS | Media (ms) | p50 (ms) "
        "| p95 (ms) | p99 (ms) | Máx (ms) | Errores | Límites |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name, result in summary["scenarios"].items():
        agg, setup = result["aggregated"], result["scenario"]
        lines.append(
            f"| {name} | {setup['users']} | {setup['seconds']} | {agg['requests']} | "
            f"{agg['rps']} | {agg['mean_ms']} | {agg['p50_ms']} | {agg['p95_ms']} | "
            f"{agg['p99_ms']} | {agg['max_ms']} | {agg['error_rate_pct']} % | "
            f"{'cumple' if result['evaluation']['passed'] else 'NO cumple'} |"
        )
    limits = next(iter(summary["scenarios"].values()))["evaluation"]["limits"]
    lines += [
        "",
        f"Límites: p95 ≤ {limits['p95_ms']:g} ms y tasa de error ≤ {limits['error_rate_pct']:g} %.",
    ]
    for name, result in summary["scenarios"].items():
        lines += [
            "",
            f"## Escenario `{name}` por endpoint",
            "",
            "| Endpoint | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) "
            "| Máx (ms) | Errores |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for endpoint, row in result["endpoints"].items():
            lines.append(
                f"| `{endpoint}` | {row['requests']} | {row['rps']} | {row['mean_ms']} | "
                f"{row['p50_ms']} | {row['p95_ms']} | {row['p99_ms']} | {row['max_ms']} | "
                f"{row['failures']} ({row['error_rate_pct']} %) |"
            )
        if result["failures"]:
            lines += ["", "Errores observados:", ""]
            lines += [
                f"- `{item['endpoint']}`: {item['error']} ({item['occurrences']} veces)"
                for item in result["failures"]
            ]
    return "\n".join(lines) + "\n"


def locust_version():
    try:
        from importlib.metadata import version

        return version("locust")
    except Exception:
        return "desconocida"


def check_health(host, timeout=10):
    if not host.startswith(("http://", "https://")):
        raise LoadTestError(f"El host debe empezar con http:// o https://: {host}")
    try:
        response = requests.get(host.rstrip("/") + "/health", timeout=timeout)
    except requests.RequestException as error:
        raise LoadTestError(
            f"No se pudo consultar {host}/health ({error}). "
            "Levanta la API con `docker compose up -d --wait` antes de medir."
        ) from error
    if response.status_code != 200:
        raise LoadTestError(f"/health respondió HTTP {response.status_code}")


def locust_command(name, scenario, host, directory):
    prefix = Path(directory) / name
    return [
        sys.executable,
        "-m",
        "locust",
        "-f",
        str(LOCUSTFILE),
        "--headless",
        "--host",
        host,
        "--users",
        str(scenario["users"]),
        "--spawn-rate",
        str(scenario["spawn_rate"]),
        "--run-time",
        f"{scenario['seconds']}s",
        "--csv",
        str(prefix),
        "--html",
        str(prefix.with_suffix(".html")),
        "--exit-code-on-error",
        "0",
    ]


def run(host, names, seconds=None, directory=OUTPUT, limits=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    check_health(host)
    results = {}
    for name in names:
        scenario = {**SCENARIOS[name], **({"seconds": seconds} if seconds else {})}
        print(f"== {name}: {scenario['users']} usuarios, {scenario['seconds']} s ==", flush=True)
        completed = subprocess.run(locust_command(name, scenario, host, directory), check=False)
        if completed.returncode != 0:
            raise LoadTestError(f"Locust terminó con código {completed.returncode} en {name}")
        results[name] = summarize_scenario(name, scenario, directory, limits)
    summary = {
        "host": host,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "locust": locust_version(),
        "scenarios": results,
    }
    (directory / "resumen.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (directory / "resumen.md").write_text(render_markdown(summary), encoding="utf-8")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="http://127.0.0.1:8000")
    parser.add_argument("--scenario", nargs="+", choices=SCENARIOS, default=list(SCENARIOS))
    parser.add_argument("--seconds", type=int, help="Reemplaza la duración de los escenarios")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--p95-ms", type=float, default=LIMITS["p95_ms"])
    parser.add_argument("--max-error-pct", type=float, default=LIMITS["error_rate_pct"])
    args = parser.parse_args(argv)
    limits = {"p95_ms": args.p95_ms, "error_rate_pct": args.max_error_pct}
    try:
        summary = run(args.host, args.scenario, args.seconds, args.output, limits)
    except LoadTestError as error:
        print(error, file=sys.stderr)
        return 2
    for name, result in summary["scenarios"].items():
        agg = result["aggregated"]
        print(
            f"{name}: {agg['requests']} peticiones, {agg['rps']} RPS, p95 {agg['p95_ms']} ms, "
            f"errores {agg['error_rate_pct']} %, "
            f"{'cumple' if result['evaluation']['passed'] else 'NO cumple'}"
        )
    return 0 if all(r["evaluation"]["passed"] for r in summary["scenarios"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
