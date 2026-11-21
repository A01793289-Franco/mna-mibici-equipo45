# Pruebas de carga con Locust

**Host:** `http://127.0.0.1:8000` · **Fecha (UTC):** 2026-11-21 17:08 · **Locust:** 2.46.0

## Resumen por escenario

| Escenario | Usuarios | Duración (s) | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores | Límites |
|---|---|---|---|---|---|---|---|---|---|---|---|
| estres | 100 | 120 | 25187 | 211.27 | 164.2 | 130.0 | 410.0 | 520.0 | 805.1 | 0.0 % | cumple |

Límites: p95 ≤ 500 ms y tasa de error ≤ 1 %.

## Recursos durante cada escenario

| Escenario | Servicio | Muestras | CPU media (%) | CPU p95 (%) | CPU máx (%) | Memoria media (MiB) | Memoria máx (MiB) | Memoria máx (%) | PIDS máx |
|---|---|---|---|---|---|---|---|---|---|
| estres | api | 60 | 124.54 | 128.3 | 138.26 | 228.4 | 230.9 | 22.55 | 85 |
| estres | mlflow | 60 | 1.58 | 3.12 | 10.97 | 1012.0 | 1020.4 | 99.69 | 118 |

CPU en % de un núcleo, como lo reporta `stats` (puede superar 100 %).

## Escenario `estres` por endpoint

| Endpoint | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores |
|---|---|---|---|---|---|---|---|---|
| `/health` | 2490 | 20.89 | 48.0 | 41.0 | 110.0 | 160.0 | 462.0 | 0 (0.0 %) |
| `/predict/p1` | 12485 | 104.73 | 261.1 | 260.0 | 450.0 | 550.0 | 805.1 | 0 (0.0 %) |
| `/predict/p1 [invalida]` | 2552 | 21.41 | 31.0 | 24.0 | 75.0 | 98.0 | 292.3 | 0 (0.0 %) |
| `/predict/p2` | 7660 | 64.25 | 88.3 | 78.0 | 200.0 | 280.0 | 563.1 | 0 (0.0 %) |
