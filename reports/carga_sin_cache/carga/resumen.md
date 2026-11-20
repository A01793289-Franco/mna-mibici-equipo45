# Pruebas de carga con Locust

**Host:** `http://127.0.0.1:8000` · **Fecha (UTC):** 2026-11-20 11:07 · **Locust:** 2.46.0

## Resumen por escenario

| Escenario | Usuarios | Duración (s) | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores | Límites |
|---|---|---|---|---|---|---|---|---|---|---|---|
| carga | 25 | 120 | 6152 | 51.79 | 171.5 | 9.0 | 680.0 | 3700.0 | 5521.9 | 0.0 % | NO cumple |

Límites: p95 ≤ 500 ms y tasa de error ≤ 1 %.

## Escenario `carga` por endpoint

| Endpoint | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores |
|---|---|---|---|---|---|---|---|---|
| `/health` | 584 | 4.92 | 3.5 | 3.0 | 8.0 | 13.0 | 38.4 | 0 (0.0 %) |
| `/predict/p1` | 3026 | 25.48 | 317.9 | 12.0 | 3200.0 | 4100.0 | 5521.9 | 0 (0.0 %) |
| `/predict/p1 [invalida]` | 658 | 5.54 | 2.9 | 2.0 | 6.0 | 14.0 | 161.1 | 0 (0.0 %) |
| `/predict/p2` | 1884 | 15.86 | 47.5 | 10.0 | 340.0 | 720.0 | 2095.5 | 0 (0.0 %) |
