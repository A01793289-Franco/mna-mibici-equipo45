import json

import pytest

from mibici import load_test

STATS_HEADER = (
    "Type,Name,Request Count,Failure Count,Median Response Time,Average Response Time,"
    "Min Response Time,Max Response Time,Average Content Size,Requests/s,Failures/s,"
    "50%,66%,75%,80%,90%,95%,98%,99%,99.9%,99.99%,100%"
)


def stats_row(name, requests, failures, rps, mean, p50, p95, p99, maximum):
    return (
        f"POST,{name},{requests},{failures},{p50},{mean},1,{maximum},100,{rps},0,"
        f"{p50},{p50},{p50},{p50},{p95},{p95},{p99},{p99},{p99},{p99},{maximum}"
    )


@pytest.fixture
def directory(tmp_path):
    rows = [
        stats_row("/predict/p1", 600, 0, 6.0, 12.0, 10, 30, 60, 90),
        stats_row("/predict/p2", 400, 10, 4.0, 15.0, 12, 40, 80, 120),
        stats_row("Aggregated", 1000, 10, 10.0, 13.2, 11, 35, 70, 120),
    ]
    (tmp_path / "carga_stats.csv").write_text(
        "\n".join([STATS_HEADER, *rows]) + "\n", encoding="utf-8"
    )
    (tmp_path / "carga_failures.csv").write_text(
        "Method,Name,Error,Occurrences\nPOST,/predict/p2,HTTP 503,10\n", encoding="utf-8"
    )
    return tmp_path


SCENARIO = {"users": 25, "spawn_rate": 5, "seconds": 120}


def test_parse_stats_reads_each_endpoint_and_aggregate(directory):
    endpoints = load_test.parse_stats(directory / "carga_stats.csv")
    assert set(endpoints) == {"/predict/p1", "/predict/p2", "Aggregated"}
    assert endpoints["/predict/p2"]["error_rate_pct"] == 2.5
    assert endpoints["Aggregated"]["p95_ms"] == 35.0
    assert endpoints["Aggregated"]["rps"] == 10.0


def test_parse_stats_requires_aggregated_row(tmp_path):
    (tmp_path / "x_stats.csv").write_text(
        "\n".join([STATS_HEADER, stats_row("/predict/p1", 1, 0, 1, 1, 1, 1, 1, 1)]) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(load_test.LoadTestError):
        load_test.parse_stats(tmp_path / "x_stats.csv")


def test_summary_reports_failures_and_limits(directory):
    result = load_test.summarize_scenario("carga", SCENARIO, directory)
    assert "Aggregated" not in result["endpoints"]
    assert result["failures"] == [
        {"endpoint": "/predict/p2", "error": "HTTP 503", "occurrences": 10}
    ]
    # 1 % de error exacto cumple; el p95 de 35 ms también.
    assert result["evaluation"]["passed"] is True


def test_evaluate_fails_when_latency_or_errors_exceed_limits():
    slow = {"p95_ms": 900.0, "error_rate_pct": 0.0}
    failing = {"p95_ms": 10.0, "error_rate_pct": 5.0}
    assert load_test.evaluate(slow)["checks"] == {"p95_ms": False, "error_rate_pct": True}
    assert load_test.evaluate(failing)["passed"] is False


def test_missing_failures_file_means_no_errors(tmp_path):
    assert load_test.parse_failures(tmp_path / "nada_failures.csv") == []


def test_markdown_contains_metrics_and_verdict(directory):
    summary = {
        "host": "http://127.0.0.1:8000",
        "generated_at": "2026-11-20 10:00",
        "locust": "2.46.0",
        "scenarios": {"carga": load_test.summarize_scenario("carga", SCENARIO, directory)},
    }
    markdown = load_test.render_markdown(summary)
    assert "| carga | 25 | 120 | 1000 | 10.0 |" in markdown
    assert "`/predict/p2`" in markdown
    assert "cumple" in markdown
    assert "HTTP 503 (10 veces)" in markdown
    json.dumps(summary)


def test_locust_command_is_headless_and_tolerates_exit_code(tmp_path):
    command = load_test.locust_command("carga", SCENARIO, "http://x:8000", tmp_path)
    assert command[1:3] == ["-m", "locust"]
    assert "--headless" in command
    assert command[command.index("--users") + 1] == "25"
    assert command[command.index("--run-time") + 1] == "120s"
    assert command[command.index("--exit-code-on-error") + 1] == "0"


def test_scenarios_grow_in_load():
    users = [load_test.SCENARIOS[n]["users"] for n in ("baseline", "carga", "estres")]
    assert users == sorted(users) and len(set(users)) == 3


def test_check_health_explains_unreachable_host():
    with pytest.raises(load_test.LoadTestError, match="docker compose up"):
        load_test.check_health("http://127.0.0.1:9", timeout=1)


def test_reads_cp1252_csv_written_by_locust_on_windows(tmp_path):
    rows = [stats_row("/predict/p1 [inválida]", 10, 0, 1.0, 5.0, 5, 8, 9, 9)]
    rows.append(stats_row("Aggregated", 10, 0, 1.0, 5.0, 5, 8, 9, 9))
    (tmp_path / "x_stats.csv").write_bytes(
        ("\n".join([STATS_HEADER, *rows]) + "\n").encode("cp1252")
    )
    assert "/predict/p1 [inválida]" in load_test.parse_stats(tmp_path / "x_stats.csv")


def test_check_health_rejects_non_http_hosts():
    with pytest.raises(load_test.LoadTestError, match="http"):
        load_test.check_health("file:///etc/passwd")
