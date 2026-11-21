# Pruebas de carga con Locust

**Host:** `http://127.0.0.1:8000` · **Fecha (UTC):** 2026-11-21 17:17 · **Locust:** 2.46.0

## Resumen por escenario

| Escenario | Usuarios | Duración (s) | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores | Límites |
|---|---|---|---|---|---|---|---|---|---|---|---|
| estres | 100 | 120 | 256 | 2.17 | 31241.4 | 23000.0 | 73000.0 | 75000.0 | 75418.2 | 0.0 % | NO cumple |

Límites: p95 ≤ 500 ms y tasa de error ≤ 1 %.

## Recursos durante cada escenario

| Escenario | Servicio | Muestras | CPU media (%) | CPU p95 (%) | CPU máx (%) | Memoria media (MiB) | Memoria máx (MiB) | Memoria máx (%) | PIDS máx |
|---|---|---|---|---|---|---|---|---|---|
| estres | api | 60 | 105.39 | 112.21 | 114.82 | 506.5 | 630.2 | 61.55 | 1026 |
| estres | mlflow | 60 | 24.15 | 45.81 | 57.1 | 1012.3 | 1024.2 | 100.0 | 141 |

CPU en % de un núcleo, como lo reporta `stats` (puede superar 100 %).

## Escenario `estres` por endpoint

| Endpoint | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores |
|---|---|---|---|---|---|---|---|---|
| `/health` | 34 | 0.29 | 11628.9 | 13000.0 | 27000.0 | 27000.0 | 27344.0 | 0 (0.0 %) |
| `/predict/p1` | 111 | 0.94 | 40740.1 | 46000.0 | 73000.0 | 75000.0 | 75418.2 | 0 (0.0 %) |
| `/predict/p1 [invalida]` | 39 | 0.33 | 14.1 | 8.0 | 45.0 | 47.0 | 47.1 | 0 (0.0 %) |
| `/predict/p2` | 72 | 0.61 | 42773.8 | 46000.0 | 73000.0 | 75000.0 | 74880.7 | 0 (0.0 %) |
