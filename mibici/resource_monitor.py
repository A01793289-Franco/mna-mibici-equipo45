"""Muestrea CPU y memoria de los contenedores con ``docker stats`` o ``podman stats``.

Uso independiente (por ejemplo, para medir el consumo en reposo)::

    python -m mibici.resource_monitor --engine docker --seconds 60 \\
        --output reports/recursos/con_cache/reposo

``mibici.load_test --stats docker`` usa el mismo muestreador mientras corre Locust.
Cada muestra es una lectura de ``stats --no-stream``; el resumen da media, p95 y máximo
por servicio a lo largo de toda la medición, no una captura al terminar.

Docker calcula el % de CPU del momento. Podman, con ``--no-stream``, reporta el promedio
desde que arrancó el contenedor; por eso con Podman la CPU se calcula entre dos lecturas
consecutivas del contador acumulado ``CPUNano`` y la primera lectura de cada contenedor
solo sirve de referencia.
"""

import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time

# Docker nombra el campo de procesos ``PIDs``; Podman, ``PIDS``. Podman agrega ``CPUNano``,
# el tiempo de CPU acumulado en nanosegundos.
TEMPLATES = {
    "docker": "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}|{{.PIDs}}",
    "podman": "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}|{{.PIDS}}|{{.CPUNano}}",
}
SERVICES = ("api", "mlflow")
FIELDS = [
    "elapsed_s",
    "service",
    "container",
    "cpu_pct",
    "mem_mib",
    "mem_limit_mib",
    "mem_pct",
    "pids",
]
# Docker usa unidades binarias (MiB); Podman, decimales (MB). Todo se normaliza a MiB.
UNITS = {
    "b": 1,
    "kib": 1024,
    "mib": 1024**2,
    "gib": 1024**3,
    "tib": 1024**4,
    "kb": 1000,
    "mb": 1000**2,
    "gb": 1000**3,
    "tb": 1000**4,
}
SIZE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*([a-zA-Z]+)\s*$")


class MonitorError(RuntimeError):
    pass


def parse_size(text):
    """Convierte ``830.6MiB``, ``1GiB`` o ``1.069MB`` a MiB."""
    match = SIZE.match(text)
    if not match or match.group(2).lower() not in UNITS:
        raise MonitorError(f"Tamaño no reconocido: {text!r}")
    return float(match.group(1)) * UNITS[match.group(2).lower()] / 1024**2


def parse_percent(text):
    text = text.strip().rstrip("%")
    return float(text) if text not in ("", "--") else 0.0


def service_of(container, services=SERVICES):
    """Servicio de Compose al que pertenece un contenedor, según su nombre."""
    parts = re.split(r"[-_]", container.lower())
    for service in services:
        if service in parts:
            return service
    return None


def parse_line(line, services=SERVICES):
    """Una línea de ``stats`` con la plantilla de ``TEMPLATES``; ``None`` si no interesa."""
    fields = [field.strip() for field in line.strip().split("|")]
    if len(fields) not in (5, 6):
        return None
    name, cpu, usage, mem_pct, pids = fields[:5]
    service = service_of(name, services)
    if service is None:
        return None
    used, _, limit = usage.partition("/")
    row = {
        "service": service,
        "container": name,
        "cpu_pct": parse_percent(cpu),
        "mem_mib": round(parse_size(used), 1),
        "mem_limit_mib": round(parse_size(limit), 1) if limit.strip() else None,
        "mem_pct": parse_percent(mem_pct),
        "pids": int(pids) if pids.isdigit() else 0,
    }
    if len(fields) == 6:
        row["cpu_nano"] = int(fields[5]) if fields[5].isdigit() else None
    return row


def cpu_from_counters(rows, previous, now):
    """Sustituye el % de CPU por el del intervalo desde la lectura anterior (Podman).

    ``previous`` guarda, por contenedor, el último ``(cpu_nano, instante)``. Las filas sin
    lectura anterior válida (la primera, o tras un reinicio que reinicia el contador) se
    descartan. Las filas sin ``cpu_nano`` (Docker) se devuelven sin cambios.
    """
    result = []
    for row in rows:
        row = dict(row)
        if "cpu_nano" not in row:
            result.append(row)
            continue
        nano = row.pop("cpu_nano")
        last = previous.get(row["container"])
        previous[row["container"]] = (nano, now)
        if nano is None or last is None or last[0] is None or nano < last[0] or now <= last[1]:
            continue
        row["cpu_pct"] = round(100 * (nano - last[0]) / ((now - last[1]) * 1e9), 2)
        result.append(row)
    return result


def percentile(values, q):
    """Percentil por el método del rango más cercano, como en los reportes de Locust."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q / 100 * len(ordered)) - 1)]


def summarize(rows):
    """Media, p95 y máximo de CPU y memoria por servicio."""
    summary = {}
    for service in sorted({row["service"] for row in rows}):
        selected = [row for row in rows if row["service"] == service]
        cpu = [row["cpu_pct"] for row in selected]
        mem = [row["mem_mib"] for row in selected]
        mem_pct = [row["mem_pct"] for row in selected]
        summary[service] = {
            "samples": len(selected),
            "cpu_pct": {
                "mean": round(sum(cpu) / len(cpu), 2),
                "p95": round(percentile(cpu, 95), 2),
                "max": round(max(cpu), 2),
            },
            "mem_mib": {
                "mean": round(sum(mem) / len(mem), 1),
                "p95": round(percentile(mem, 95), 1),
                "max": round(max(mem), 1),
            },
            "mem_pct_max": round(max(mem_pct), 2),
            "mem_limit_mib": selected[-1]["mem_limit_mib"],
            "pids_max": max(row["pids"] for row in selected),
        }
    return summary


def stats_command(engine):
    executable = shutil.which(engine)
    if executable is None:
        raise MonitorError(f"No se encontró `{engine}` en el PATH.")
    return [executable, "stats", "--no-stream", "--format", TEMPLATES[engine]]


def read_stats(command, services=SERVICES, timeout=30):
    completed = subprocess.run(
        command, capture_output=True, text=True, timeout=timeout, check=False
    )
    if completed.returncode != 0:
        raise MonitorError(
            f"`stats` terminó con código {completed.returncode}: {completed.stderr}"
        )
    rows = [parse_line(line, services) for line in completed.stdout.splitlines()]
    return [row for row in rows if row]


class Sampler:
    """Lee ``stats`` cada ``interval`` segundos en un hilo, hasta llamar a ``stop()``."""

    def __init__(self, engine="docker", interval=2.0, services=SERVICES, reader=None):
        self.interval = interval
        self.services = services
        if reader is None:
            command = stats_command(engine)

            def reader():
                return read_stats(command, services)

        self.reader = reader
        self.rows = []
        self.errors = []
        self._counters = {}
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        start = time.monotonic()
        while not self._stop.is_set():
            tick = time.monotonic()
            try:
                rows = cpu_from_counters(self.reader(), self._counters, time.monotonic())
                for row in rows:
                    self.rows.append({"elapsed_s": round(tick - start, 1), **row})
            except (MonitorError, subprocess.TimeoutExpired, OSError) as error:
                self.errors.append(str(error))
            self._stop.wait(max(0.0, self.interval - (time.monotonic() - tick)))

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self.stop()

    def stop(self):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join()
        return self.rows


def write_csv(rows, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def plot(rows, path, title):
    """Serie de tiempo de CPU y memoria por servicio, en PNG."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, (cpu_axis, mem_axis) = plt.subplots(2, 1, figsize=(8, 5.5), sharex=True)
    for service in sorted({row["service"] for row in rows}):
        selected = [row for row in rows if row["service"] == service]
        elapsed = [row["elapsed_s"] for row in selected]
        cpu_axis.plot(elapsed, [row["cpu_pct"] for row in selected], label=service)
        mem_axis.plot(elapsed, [row["mem_mib"] for row in selected], label=service)
        limit = selected[-1]["mem_limit_mib"]
        if limit:
            mem_axis.axhline(limit, linestyle="--", linewidth=0.8, color="grey")
    cpu_axis.set_ylabel("CPU (%)")
    mem_axis.set_ylabel("Memoria (MiB)")
    mem_axis.set_xlabel("Segundos desde el inicio")
    cpu_axis.set_title(title)
    cpu_axis.legend(loc="upper left")
    for axis in (cpu_axis, mem_axis):
        axis.set_ylim(bottom=0)
        axis.grid(alpha=0.3)
    figure.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=110)
    plt.close(figure)


def save(rows, errors, directory, name, engine, interval):
    """Escribe ``{name}_recursos.csv``, ``.json`` y ``.png``; devuelve el resumen."""
    directory = Path(directory)
    write_csv(rows, directory / f"{name}_recursos.csv")
    result = {
        "engine": engine,
        "interval_s": interval,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "services": summarize(rows),
        "errors": errors,
    }
    (directory / f"{name}_recursos.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if rows:
        plot(rows, directory / f"{name}_recursos.png", f"Recursos — {name}")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--engine", choices=TEMPLATES, default="docker")
    parser.add_argument("--seconds", type=float, default=60)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--name", default="reposo")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        sampler = Sampler(args.engine, args.interval)
    except MonitorError as error:
        print(error, file=sys.stderr)
        return 2
    with sampler:
        time.sleep(args.seconds)
    if not sampler.rows:
        print("No se obtuvieron muestras de api ni de mlflow.", file=sys.stderr)
        return 2
    result = save(sampler.rows, sampler.errors, args.output, args.name, args.engine, args.interval)
    for service, values in result["services"].items():
        print(
            f"{service}: CPU media {values['cpu_pct']['mean']} %, "
            f"memoria máx {values['mem_mib']['max']} MiB ({values['mem_pct_max']} %)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
