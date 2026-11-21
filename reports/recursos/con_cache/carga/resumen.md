# Pruebas de carga con Locust

**Host:** `http://127.0.0.1:8000` · **Fecha (UTC):** 2026-11-21 17:05 · **Locust:** 2.46.0

## Resumen por escenario

| Escenario | Usuarios | Duración (s) | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores | Límites |
|---|---|---|---|---|---|---|---|---|---|---|---|
| carga | 25 | 120 | 8474 | 71.07 | 43.7 | 47.0 | 55.0 | 62.0 | 647.8 | 0.0 % | cumple |

Límites: p95 ≤ 500 ms y tasa de error ≤ 1 %.

## Recursos durante cada escenario

| Escenario | Servicio | Muestras | CPU media (%) | CPU p95 (%) | CPU máx (%) | Memoria media (MiB) | Memoria máx (MiB) | Memoria máx (%) | PIDS máx |
|---|---|---|---|---|---|---|---|---|---|
| carga | api | 60 | 36.65 | 44.37 | 48.32 | 213.3 | 218.0 | 21.29 | 17 |
| carga | mlflow | 60 | 1.44 | 2.88 | 10.94 | 1012.3 | 1024.2 | 99.99 | 121 |

CPU en % de un núcleo, como lo reporta `stats` (puede superar 100 %).

## Escenario `carga` por endpoint

| Endpoint | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores |
|---|---|---|---|---|---|---|---|---|
| `/health` | 820 | 6.88 | 2.0 | 2.0 | 4.0 | 7.0 | 79.4 | 0 (0.0 %) |
| `/predict/p1` | 4249 | 35.63 | 50.1 | 49.0 | 57.0 | 65.0 | 647.8 | 0 (0.0 %) |
| `/predict/p1 [invalida]` | 835 | 7.0 | 44.1 | 44.0 | 49.0 | 50.0 | 115.5 | 0 (0.0 %) |
| `/predict/p2` | 2570 | 21.55 | 46.2 | 45.0 | 50.0 | 53.0 | 618.5 | 0 (0.0 %) |
