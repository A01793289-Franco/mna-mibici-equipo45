# Pruebas de carga con Locust

**Host:** `http://127.0.0.1:8000` · **Fecha (UTC):** 2026-11-20 11:09 · **Locust:** 2.46.0

## Resumen por escenario

| Escenario | Usuarios | Duración (s) | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores | Límites |
|---|---|---|---|---|---|---|---|---|---|---|---|
| estres | 100 | 120 | 11654 | 97.5 | 706.1 | 390.0 | 590.0 | 13000.0 | 16994.8 | 0.0 % | NO cumple |

Límites: p95 ≤ 500 ms y tasa de error ≤ 1 %.

## Escenario `estres` por endpoint

| Endpoint | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores |
|---|---|---|---|---|---|---|---|---|
| `/health` | 1171 | 9.8 | 187.9 | 75.0 | 170.0 | 3300.0 | 5236.0 | 0 (0.0 %) |
| `/predict/p1` | 5756 | 48.15 | 915.1 | 390.0 | 680.0 | 15000.0 | 16994.8 | 0 (0.0 %) |
| `/predict/p1 [invalida]` | 1142 | 9.55 | 16.8 | 16.0 | 33.0 | 42.0 | 84.5 | 0 (0.0 %) |
| `/predict/p2` | 3585 | 29.99 | 759.4 | 460.0 | 2800.0 | 7000.0 | 9523.3 | 0 (0.0 %) |
