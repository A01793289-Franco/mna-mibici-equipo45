# Pruebas de carga con Locust

**Host:** `http://127.0.0.1:8000` · **Fecha (UTC):** 2026-11-20 11:04 · **Locust:** 2.46.0

## Resumen por escenario

| Escenario | Usuarios | Duración (s) | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores | Límites |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 5 | 60 | 662 | 11.14 | 127.5 | 120.0 | 320.0 | 410.0 | 463.2 | 0.0 % | cumple |

Límites: p95 ≤ 500 ms y tasa de error ≤ 1 %.

## Escenario `baseline` por endpoint

| Endpoint | Peticiones | RPS | Media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Máx (ms) | Errores |
|---|---|---|---|---|---|---|---|---|
| `/health` | 65 | 1.09 | 5.2 | 3.0 | 15.0 | 43.0 | 42.9 | 0 (0.0 %) |
| `/predict/p1` | 339 | 5.7 | 146.2 | 150.0 | 310.0 | 410.0 | 447.4 | 0 (0.0 %) |
| `/predict/p1 [invalida]` | 61 | 1.03 | 6.5 | 3.0 | 18.0 | 69.0 | 68.9 | 0 (0.0 %) |
| `/predict/p2` | 197 | 3.31 | 173.3 | 190.0 | 350.0 | 430.0 | 463.2 | 0 (0.0 %) |
