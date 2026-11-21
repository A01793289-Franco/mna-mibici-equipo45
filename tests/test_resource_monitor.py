import json
import time

import pytest

from mibici import load_test, resource_monitor

# Salidas reales: Docker Desktop (reports/carga_sin_cache) y Podman 6.1.4.
DOCKER = "mibici-equipo45-api-1|0.21%|830.6MiB / 1GiB|81.12%|39"
DOCKER_MLFLOW = "mibici-equipo45-mlflow-1|1.08%|1010MiB / 1GiB|98.59%|108"
PODMAN = "mna-mibici-equipo45_api_1|3.39%|1.069MB / 16.46GB|0.01%|1"


def test_parse_size_handles_binary_and_decimal_units():
    assert resource_monitor.parse_size("1GiB") == 1024
    assert resource_monitor.parse_size("830.6MiB") == pytest.approx(830.6)
    assert resource_monitor.parse_size("512KiB") == 0.5
    assert resource_monitor.parse_size("1.069MB") == pytest.approx(1.0195, abs=1e-4)
    with pytest.raises(resource_monitor.MonitorError):
        resource_monitor.parse_size("mucho")


def test_parse_line_reads_docker_output():
    row = resource_monitor.parse_line(DOCKER)
    assert row == {
        "service": "api",
        "container": "mibici-equipo45-api-1",
        "cpu_pct": 0.21,
        "mem_mib": 830.6,
        "mem_limit_mib": 1024.0,
        "mem_pct": 81.12,
        "pids": 39,
    }


def test_parse_line_reads_podman_compose_names():
    row = resource_monitor.parse_line(PODMAN)
    assert row["service"] == "api"
    assert row["mem_mib"] == 1.0


def test_parse_line_ignores_other_containers_and_malformed_lines():
    assert (
        resource_monitor.parse_line("mibici-equipo45-registry-init-1|0%|1MiB / 1GiB|0%|1") is None
    )
    assert resource_monitor.parse_line("rapido-1|0%|1MiB / 1GiB|0%|1") is None
    assert resource_monitor.parse_line("texto sin formato") is None
    # Podman muestra "--" mientras el contenedor arranca.
    assert resource_monitor.parse_line("x-api-1|--|1MiB / 1GiB|--|1")["cpu_pct"] == 0.0


def test_summarize_gives_mean_p95_and_max_per_service():
    rows = [
        {"elapsed_s": i, **resource_monitor.parse_line(f"p-api-1|{cpu}%|{mem}MiB / 1GiB|1%|{i}")}
        for i, (cpu, mem) in enumerate([(10, 200), (20, 300), (30, 250), (100, 260)])
    ]
    rows.append({"elapsed_s": 0, **resource_monitor.parse_line(DOCKER_MLFLOW)})
    summary = resource_monitor.summarize(rows)
    assert summary["api"]["samples"] == 4
    assert summary["api"]["cpu_pct"] == {"mean": 40.0, "p95": 100.0, "max": 100.0}
    assert summary["api"]["mem_mib"]["max"] == 300.0
    assert summary["api"]["mem_limit_mib"] == 1024.0
    assert summary["api"]["pids_max"] == 3
    assert summary["mlflow"]["mem_pct_max"] == 98.59


def test_sampler_collects_rows_and_keeps_errors():
    calls = []

    def reader():
        calls.append(1)
        if len(calls) == 2:
            raise resource_monitor.MonitorError("falló una lectura")
        return [resource_monitor.parse_line(DOCKER)]

    with resource_monitor.Sampler(interval=0.01, reader=reader) as sampler:
        while len(calls) < 4:
            time.sleep(0.005)
    assert len(sampler.rows) >= 3
    assert sampler.errors == ["falló una lectura"]
    assert sampler.rows[0]["elapsed_s"] == 0.0


def test_missing_engine_is_reported(monkeypatch):
    monkeypatch.setattr(resource_monitor.shutil, "which", lambda name: None)
    with pytest.raises(resource_monitor.MonitorError, match="podman"):
        resource_monitor.stats_command("podman")


def test_save_writes_utf8_csv_json_and_plot(tmp_path):
    rows = [
        {"elapsed_s": 0.0, **resource_monitor.parse_line(DOCKER)},
        {"elapsed_s": 2.0, **resource_monitor.parse_line(DOCKER_MLFLOW)},
    ]
    result = resource_monitor.save(rows, [], tmp_path, "carga", "docker", 2.0)
    assert set(result["services"]) == {"api", "mlflow"}
    csv_text = (tmp_path / "carga_recursos.csv").read_text(encoding="utf-8")
    assert csv_text.splitlines()[0].startswith("elapsed_s,service,container")
    saved = json.loads((tmp_path / "carga_recursos.json").read_text(encoding="utf-8"))
    assert saved["engine"] == "docker"
    assert (tmp_path / "carga_recursos.png").read_bytes()[:4] == b"\x89PNG"


def test_load_test_markdown_includes_resources_only_when_measured():
    summary = {
        "host": "http://x",
        "generated_at": "2026-11-21 10:00",
        "locust": "2.46.0",
        "scenarios": {
            "carga": {
                "scenario": {"users": 25, "seconds": 120},
                "aggregated": {
                    "requests": 1,
                    "rps": 1,
                    "mean_ms": 1,
                    "p50_ms": 1,
                    "p95_ms": 1,
                    "p99_ms": 1,
                    "max_ms": 1,
                    "error_rate_pct": 0,
                },
                "endpoints": {},
                "failures": [],
                "evaluation": load_test.evaluate({"p95_ms": 1, "error_rate_pct": 0}),
            }
        },
    }
    assert "Recursos" not in load_test.render_markdown(summary)
    rows = [{"elapsed_s": 0.0, **resource_monitor.parse_line(DOCKER)}]
    summary["scenarios"]["carga"]["resources"] = {"services": resource_monitor.summarize(rows)}
    markdown = load_test.render_markdown(summary)
    assert "## Recursos durante cada escenario" in markdown
    assert "| carga | api | 1 | 0.21 | 0.21 | 0.21 | 830.6 | 830.6 | 81.12 | 39 |" in markdown


def test_run_locust_without_stats_does_not_sample(monkeypatch):
    monkeypatch.setattr(load_test.subprocess, "run", lambda *a, **k: "hecho")
    assert load_test.run_locust(["locust"]) == ("hecho", None)
