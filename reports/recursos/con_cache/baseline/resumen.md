# Pruebas de carga con Locust

**Host:** `http://127.0.0.1:8000` · **Fecha (UTC):** 2026-11-21 17:03 · **Locust:** 2.46.0

## Resumen por escenario

| Escenario | Usuarios | Duración (s) | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores | Límites |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 5 | 60 | 838 | 14.16 | 44.6 | 48.0 | 53.0 | 56.0 | 497.4 | 0.0 % | cumple |

Límites: p95 ≤ 500 ms y tasa de error ≤ 1 %.

## Recursos durante cada escenario

| Escenario | Servicio | Muestras | CPU media (%) | CPU p95 (%) | CPU máx (%) | Memoria media (MiB) | Memoria máx (MiB) | Memoria máx (%) | PIDS máx |
|---|---|---|---|---|---|---|---|---|---|
| baseline | api | 30 | 9.19 | 11.69 | 20.78 | 209.7 | 211.8 | 20.68 | 29 |
| baseline | mlflow | 30 | 1.86 | 3.52 | 12.58 | 1011.3 | 1019.5 | 99.53 | 112 |

CPU en % de un núcleo, como lo reporta `stats` (puede superar 100 %).

## Escenario `baseline` por endpoint

| Endpoint | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores |
|---|---|---|---|---|---|---|---|---|
| `/health` | 67 | 1.13 | 2.2 | 2.0 | 3.0 | 4.0 | 4.2 | 0 (0.0 %) |
| `/predict/p1` | 438 | 7.4 | 50.4 | 49.0 | 54.0 | 57.0 | 497.4 | 0 (0.0 %) |
| `/predict/p1 [invalida]` | 75 | 1.27 | 44.0 | 44.0 | 48.0 | 50.0 | 49.8 | 0 (0.0 %) |
| `/predict/p2` | 258 | 4.36 | 46.0 | 46.0 | 50.0 | 51.0 | 135.9 | 0 (0.0 %) |
