# Pruebas de carga con Locust

**Host:** `http://127.0.0.1:8000` · **Fecha (UTC):** 2026-11-20 10:29 · **Locust:** 2.46.0

## Resumen por escenario

| Escenario | Usuarios | Duración (s) | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores | Límites |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 5 | 60 | 906 | 15.25 | 9.3 | 7.0 | 19.0 | 24.0 | 385.8 | 0.0 % | cumple |
| carga | 25 | 120 | 9274 | 78.13 | 10.4 | 8.0 | 28.0 | 41.0 | 74.7 | 0.0 % | cumple |
| estres | 100 | 120 | 18652 | 156.22 | 326.6 | 380.0 | 490.0 | 530.0 | 1370.2 | 0.0 % | cumple |

Límites: p95 ≤ 500 ms y tasa de error ≤ 1 %.

## Escenario `baseline` por endpoint

| Endpoint | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores |
|---|---|---|---|---|---|---|---|---|
| `/health` | 94 | 1.58 | 4.5 | 4.0 | 9.0 | 15.0 | 14.7 | 0 (0.0 %) |
| `/predict/p1` | 455 | 7.66 | 11.0 | 10.0 | 20.0 | 26.0 | 113.8 | 0 (0.0 %) |
| `/predict/p1 [invalida]` | 94 | 1.58 | 4.0 | 3.0 | 8.0 | 10.0 | 9.5 | 0 (0.0 %) |
| `/predict/p2` | 263 | 4.43 | 10.0 | 8.0 | 18.0 | 25.0 | 385.8 | 0 (0.0 %) |

## Escenario `carga` por endpoint

| Endpoint | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores |
|---|---|---|---|---|---|---|---|---|
| `/health` | 923 | 7.78 | 3.6 | 3.0 | 9.0 | 13.0 | 22.2 | 0 (0.0 %) |
| `/predict/p1` | 4720 | 39.76 | 13.6 | 12.0 | 34.0 | 46.0 | 74.7 | 0 (0.0 %) |
| `/predict/p1 [invalida]` | 898 | 7.57 | 2.4 | 2.0 | 6.0 | 8.0 | 9.8 | 0 (0.0 %) |
| `/predict/p2` | 2733 | 23.02 | 9.7 | 10.0 | 21.0 | 28.0 | 51.4 | 0 (0.0 %) |

## Escenario `estres` por endpoint

| Endpoint | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores |
|---|---|---|---|---|---|---|---|---|
| `/health` | 1826 | 15.29 | 73.5 | 71.0 | 130.0 | 150.0 | 1104.8 | 0 (0.0 %) |
| `/predict/p1` | 9299 | 77.89 | 372.6 | 370.0 | 450.0 | 490.0 | 1370.2 | 0 (0.0 %) |
| `/predict/p1 [invalida]` | 1910 | 16.0 | 18.1 | 15.0 | 33.0 | 48.0 | 734.6 | 0 (0.0 %) |
| `/predict/p2` | 5617 | 47.05 | 437.6 | 440.0 | 510.0 | 550.0 | 1366.3 | 0 (0.0 %) |
