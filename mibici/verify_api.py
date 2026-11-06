import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from pydantic import ValidationError
import requests

from mibici.schemas import P1Response, P2Response

P1_EXAMPLE = {
    "station_id": 2,
    "hour": 8,
    "weekday": 5,
    "is_weekend": 1,
    "month": 8,
    "departures_lag_1": 2.0,
    "departures_lag_24": 3.0,
    "departures_lag_168": 4.0,
    "departures_mean_24": 2.5,
    "departures_mean_168": 3.5,
}
P2_EXAMPLE = {
    **P1_EXAMPLE,
    "virtual_occupancy": 0.05,
    "net_flow_lag_1": -1.0,
    "net_flow_lag_24": 0.5,
}


class VerificationError(ValueError):
    pass


def verify_api(base_url, timeout=60, unavailable=False, request=None):
    send = request or requests.request
    checks = []

    def check(method, path, expected, payload=None):
        response = send(method, base_url.rstrip("/") + path, json=payload, timeout=timeout)
        if response.status_code != expected:
            raise VerificationError(
                f"{method} {path}: se esperaba HTTP {expected}; recibido {response.status_code}"
            )
        body = response.json()
        checks.append({"method": method, "path": path, "status": expected, "response": body})
        return body

    health = check("GET", "/health", 200)
    if health.get("status") != "ok":
        raise VerificationError("/health no confirmó el estado del proceso")
    spec = check("GET", "/openapi.json", 200)
    for question in ("p1", "p2"):
        operation = spec["paths"][f"/predict/{question}"]["post"]
        request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
        response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
        if not request_schema.get("$ref") or not response_schema.get("$ref"):
            raise VerificationError(f"/predict/{question} no declara los dos esquemas")

    expected = 503 if unavailable else 200
    p1 = check("POST", "/predict/p1", expected, P1_EXAMPLE)
    p2 = check("POST", "/predict/p2", expected, P2_EXAMPLE)
    if unavailable:
        if not p1.get("detail") or not p2.get("detail"):
            raise VerificationError("La respuesta 503 debe explicar la indisponibilidad")
    else:
        first = P1Response.model_validate(p1)
        second = P2Response.model_validate(p2)
        for body in (first, second):
            if not body.model_uri.startswith("models:/") or not body.model_uri.endswith(
                "@champion"
            ):
                raise VerificationError("La respuesta no identifica el alias del Registry")

    invalid = [
        ("/predict/p1", {**P1_EXAMPLE, "hour": 24}),
        ("/predict/p1", {**P1_EXAMPLE, "hour": "8"}),
        ("/predict/p1", {**P1_EXAMPLE, "departures_lag_1": -1}),
        ("/predict/p1", {**P1_EXAMPLE, "is_weekend": 0}),
        ("/predict/p1", {k: v for k, v in P1_EXAMPLE.items() if k != "station_id"}),
        ("/predict/p1", {**P1_EXAMPLE, "extra": 1}),
        ("/predict/p2", {**P2_EXAMPLE, "virtual_occupancy": 1.5}),
    ]
    for path, payload in invalid:
        check("POST", path, 422, payload)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "mode": "unavailable" if unavailable else "prediction",
        "passed": True,
        "checks": checks,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verifica por HTTP la API MiBici en ejecución")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="URL de la API")
    parser.add_argument("--timeout", type=float, default=60, help="Segundos por petición")
    parser.add_argument("--output", type=Path, help="Archivo JSON de evidencia")
    parser.add_argument(
        "--unavailable", action="store_true", help="Espera 503 al predecir sin Registry"
    )
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout debe ser mayor que cero")
    try:
        result = verify_api(args.base_url, args.timeout, args.unavailable)
    except (requests.RequestException, ValidationError, KeyError, ValueError) as error:
        result = {"passed": False, "error": str(error)}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
