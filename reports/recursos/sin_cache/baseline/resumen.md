# Pruebas de carga con Locust

**Host:** `http://127.0.0.1:8000` · **Fecha (UTC):** 2026-11-21 17:11 · **Locust:** 2.46.0

## Resumen por escenario

| Escenario | Usuarios | Duración (s) | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores | Límites |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 5 | 60 | 230 | 3.89 | 917.6 | 960.0 | 2100.0 | 2400.0 | 2550.6 | 0.0 % | NO cumple |

Límites: p95 ≤ 500 ms y tasa de error ≤ 1 %.

## Recursos durante cada escenario

| Escenario | Servicio | Muestras | CPU media (%) | CPU p95 (%) | CPU máx (%) | Memoria media (MiB) | Memoria máx (MiB) | Memoria máx (%) | PIDS máx |
|---|---|---|---|---|---|---|---|---|---|
| baseline | api | 30 | 99.58 | 108.13 | 109.45 | 391.5 | 499.2 | 48.74 | 411 |
| baseline | mlflow | 30 | 33.8 | 55.52 | 60.73 | 1015.0 | 1024.2 | 99.98 | 124 |

CPU en % de un núcleo, como lo reporta `stats` (puede superar 100 %).

## Escenario `baseline` por endpoint

| Endpoint | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores |
|---|---|---|---|---|---|---|---|---|
| `/health` | 29 | 0.49 | 3.1 | 2.0 | 9.0 | 16.0 | 16.1 | 0 (0.0 %) |
| `/predict/p1` | 109 | 1.84 | 1220.1 | 1300.0 | 2100.0 | 2400.0 | 2550.6 | 0 (0.0 %) |
| `/predict/p1 [invalida]` | 28 | 0.47 | 14.9 | 2.0 | 50.0 | 50.0 | 50.2 | 0 (0.0 %) |
| `/predict/p2` | 64 | 1.08 | 1211.7 | 1300.0 | 2100.0 | 2500.0 | 2464.7 | 0 (0.0 %) |
