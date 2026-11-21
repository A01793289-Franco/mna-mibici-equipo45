# Pruebas de carga con Locust

**Host:** `http://127.0.0.1:8000` · **Fecha (UTC):** 2026-11-21 17:14 · **Locust:** 2.46.0

## Resumen por escenario

| Escenario | Usuarios | Duración (s) | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores | Límites |
|---|---|---|---|---|---|---|---|---|---|---|---|
| carga | 25 | 120 | 266 | 2.24 | 9664.8 | 9600.0 | 22000.0 | 24000.0 | 25404.0 | 0.0 % | NO cumple |

Límites: p95 ≤ 500 ms y tasa de error ≤ 1 %.

## Recursos durante cada escenario

| Escenario | Servicio | Muestras | CPU media (%) | CPU p95 (%) | CPU máx (%) | Memoria media (MiB) | Memoria máx (MiB) | Memoria máx (%) | PIDS máx |
|---|---|---|---|---|---|---|---|---|---|
| carga | api | 60 | 105.62 | 112.69 | 114.19 | 486.0 | 592.1 | 57.83 | 950 |
| carga | mlflow | 60 | 23.57 | 41.86 | 70.48 | 1013.1 | 1024.2 | 100.0 | 140 |

CPU en % de un núcleo, como lo reporta `stats` (puede superar 100 %).

## Escenario `carga` por endpoint

| Endpoint | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores |
|---|---|---|---|---|---|---|---|---|
| `/health` | 30 | 0.25 | 3.5 | 3.0 | 10.0 | 11.0 | 11.4 | 0 (0.0 %) |
| `/predict/p1` | 130 | 1.1 | 12381.9 | 12000.0 | 23000.0 | 24000.0 | 24594.7 | 0 (0.0 %) |
| `/predict/p1 [invalida]` | 31 | 0.26 | 10.0 | 2.0 | 47.0 | 48.0 | 48.1 | 0 (0.0 %) |
| `/predict/p2` | 75 | 0.63 | 12810.4 | 12000.0 | 22000.0 | 25000.0 | 25404.0 | 0 (0.0 %) |
