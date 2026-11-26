# Pruebas de carga con Locust

**Host:** `http://127.0.0.1:8126` · **Fecha (UTC):** 2026-11-26 07:55 · **Locust:** 2.46.0

## Resumen por escenario

| Escenario | Usuarios | Duración (s) | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores | Límites |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 5 | 60 | 932 | 15.79 | 5.0 | 5.0 | 8.0 | 11.0 | 16.2 | 0.0 % | cumple |
| estres | 100 | 120 | 33358 | 280.08 | 50.9 | 17.0 | 200.0 | 270.0 | 452.5 | 0.0 % | cumple |

Límites: p95 ≤ 500 ms y tasa de error ≤ 1 %.

## Recursos durante cada escenario

| Escenario | Servicio | Muestras | CPU media (%) | CPU p95 (%) | CPU máx (%) | Memoria media (MiB) | Memoria máx (MiB) | Memoria máx (%) | PIDS máx |
|---|---|---|---|---|---|---|---|---|---|
| baseline | api | 31 | 9.92 | 17.14 | 17.79 | 220.1 | 220.9 | 21.57 | 26 |
| baseline | mlflow | 31 | 1.07 | 6.33 | 6.38 | 374.8 | 375.4 | 36.66 | 13 |
| estres | api | 61 | 106.61 | 116.85 | 142.93 | 237.7 | 247.7 | 24.19 | 86 |
| estres | mlflow | 61 | 1.31 | 6.32 | 6.94 | 375.7 | 376.6 | 36.77 | 13 |

CPU en % de un núcleo, como lo reporta `stats` (puede superar 100 %).

## Escenario `baseline` por endpoint

| Endpoint | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores |
|---|---|---|---|---|---|---|---|---|
| `/health` | 91 | 1.54 | 2.4 | 2.0 | 3.0 | 10.0 | 10.1 | 0 (0.0 %) |
| `/predict/p1` | 456 | 7.73 | 7.2 | 7.0 | 10.0 | 12.0 | 16.2 | 0 (0.0 %) |
| `/predict/p1 [invalida]` | 101 | 1.71 | 2.2 | 2.0 | 3.0 | 3.0 | 3.1 | 0 (0.0 %) |
| `/predict/p2` | 284 | 4.81 | 3.4 | 3.0 | 4.0 | 6.0 | 10.7 | 0 (0.0 %) |

## Escenario `estres` por endpoint

| Endpoint | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores |
|---|---|---|---|---|---|---|---|---|
| `/health` | 3397 | 28.52 | 9.9 | 4.0 | 38.0 | 65.0 | 196.9 | 0 (0.0 %) |
| `/predict/p1` | 16748 | 140.62 | 88.4 | 65.0 | 230.0 | 290.0 | 452.5 | 0 (0.0 %) |
| `/predict/p1 [invalida]` | 3279 | 27.53 | 5.1 | 2.0 | 17.0 | 32.0 | 154.4 | 0 (0.0 %) |
| `/predict/p2` | 9934 | 83.41 | 16.8 | 7.0 | 62.0 | 110.0 | 279.6 | 0 (0.0 %) |
