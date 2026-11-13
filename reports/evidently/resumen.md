# Drift y calidad de datos con Evidently

- Generado: 2026-11-13T04:41:49+00:00
- evidently 0.7.23, todas las filas, sin muestreo
- data_version `5ca52ccee062`, feature_version `87c1e6136a5f`

Referencia: periodo de entrenamiento. Actual: periodo posterior que simula producción. Solo se comparan variables de entrada; no se evalúa ningún modelo ni se usa el conjunto de prueba para decidir. month se excluye porque cada periodo cubre meses distintos. Umbrales por defecto de Evidently: 0.1 en la distancia de Wasserstein normalizada (numéricas) y de Jensen-Shannon (categóricas).

## P1: entrenamiento contra septiembre 2026

- Referencia: 2026-01-08 a 2026-06-30, 1,552,105 filas.
- Actual: 2026-09-01 a 2026-09-30, 338,690 filas.
- Variables con drift: 1 de 9 (11%); conjunto con drift: **no**.

| Variable | Tipo | Prueba | Distancia | Umbral | Drift | Media ref. | Media actual |
|---|---|---|---|---|---|---|---|
| departures_lag_1 | numérica | Wasserstein distance (normed) | 0.0581 | 0.10 | no | 1.301 | 1.444 |
| departures_lag_24 | numérica | Wasserstein distance (normed) | 0.0477 | 0.10 | no | 1.300 | 1.417 |
| departures_lag_168 | numérica | Wasserstein distance (normed) | 0.0259 | 0.10 | no | 1.290 | 1.327 |
| departures_mean_24 | numérica | Wasserstein distance (normed) | 0.0953 | 0.10 | no | 1.299 | 1.427 |
| departures_mean_168 | numérica | Wasserstein distance (normed) | 0.0859 | 0.10 | no | 1.297 | 1.368 |
| station_id | categórica | Jensen-Shannon distance | 0.2620 | 0.10 | sí | - | - |
| hour | categórica | Jensen-Shannon distance | 0.0007 | 0.10 | no | - | - |
| weekday | categórica | Jensen-Shannon distance | 0.0395 | 0.10 | no | - | - |
| is_weekend | categórica | Jensen-Shannon distance | 0.0168 | 0.10 | no | - | - |

Estaciones del periodo actual ausentes de la referencia: 58, con 12.2% de sus filas.

| Calidad | Referencia | Actual |
|---|---|---|
| Filas | 1,552,105 | 338,690 |
| Estaciones | 413 | 471 |
| Valores faltantes | 0 | 0 |
| Filas duplicadas (estación y hora) | 0 | 0 |
| Columnas constantes | ninguna | ninguna |

## P1: entrenamiento contra julio-agosto 2026

- Referencia: 2026-01-08 a 2026-06-30, 1,552,105 filas.
- Actual: 2026-07-01 a 2026-08-31, 665,747 filas.
- Variables con drift: 2 de 9 (22%); conjunto con drift: **no**.

| Variable | Tipo | Prueba | Distancia | Umbral | Drift | Media ref. | Media actual |
|---|---|---|---|---|---|---|---|
| departures_lag_1 | numérica | Wasserstein distance (normed) | 0.0523 | 0.10 | no | 1.301 | 1.172 |
| departures_lag_24 | numérica | Wasserstein distance (normed) | 0.0511 | 0.10 | no | 1.300 | 1.174 |
| departures_lag_168 | numérica | Wasserstein distance (normed) | 0.0507 | 0.10 | no | 1.290 | 1.165 |
| departures_mean_24 | numérica | Wasserstein distance (normed) | 0.0949 | 0.10 | no | 1.299 | 1.174 |
| departures_mean_168 | numérica | Wasserstein distance (normed) | 0.1052 | 0.10 | sí | 1.297 | 1.173 |
| station_id | categórica | Jensen-Shannon distance | 0.2285 | 0.10 | sí | - | - |
| hour | categórica | Jensen-Shannon distance | 0.0005 | 0.10 | no | - | - |
| weekday | categórica | Jensen-Shannon distance | 0.0161 | 0.10 | no | - | - |
| is_weekend | categórica | Jensen-Shannon distance | 0.0022 | 0.10 | no | - | - |

Estaciones del periodo actual ausentes de la referencia: 57, con 7.7% de sus filas.

| Calidad | Referencia | Actual |
|---|---|---|
| Filas | 1,552,105 | 665,747 |
| Estaciones | 413 | 470 |
| Valores faltantes | 0 | 0 |
| Filas duplicadas (estación y hora) | 0 | 0 |
| Columnas constantes | ninguna | ninguna |

## P2: entrenamiento contra septiembre 2026

- Referencia: 2026-01-08 a 2026-06-30, 1,551,437 filas.
- Actual: 2026-09-01 a 2026-09-30, 337,250 filas.
- Variables con drift: 1 de 12 (8%); conjunto con drift: **no**.

| Variable | Tipo | Prueba | Distancia | Umbral | Drift | Media ref. | Media actual |
|---|---|---|---|---|---|---|---|
| departures_lag_1 | numérica | Wasserstein distance (normed) | 0.0605 | 0.10 | no | 1.301 | 1.450 |
| departures_lag_24 | numérica | Wasserstein distance (normed) | 0.0501 | 0.10 | no | 1.300 | 1.423 |
| departures_lag_168 | numérica | Wasserstein distance (normed) | 0.0258 | 0.10 | no | 1.290 | 1.333 |
| departures_mean_24 | numérica | Wasserstein distance (normed) | 0.0974 | 0.10 | no | 1.299 | 1.433 |
| departures_mean_168 | numérica | Wasserstein distance (normed) | 0.0856 | 0.10 | no | 1.298 | 1.374 |
| virtual_occupancy | numérica | Wasserstein distance (normed) | 0.0745 | 0.10 | no | 0.378 | 0.389 |
| net_flow_lag_1 | numérica | Wasserstein distance (normed) | 0.0091 | 0.10 | no | 0.000 | -0.000 |
| net_flow_lag_24 | numérica | Wasserstein distance (normed) | 0.0119 | 0.10 | no | 0.000 | -0.000 |
| station_id | categórica | Jensen-Shannon distance | 0.2605 | 0.10 | sí | - | - |
| hour | categórica | Jensen-Shannon distance | 0.0007 | 0.10 | no | - | - |
| weekday | categórica | Jensen-Shannon distance | 0.0395 | 0.10 | no | - | - |
| is_weekend | categórica | Jensen-Shannon distance | 0.0168 | 0.10 | no | - | - |

Estaciones del periodo actual ausentes de la referencia: 58, con 12.3% de sus filas.

| Calidad | Referencia | Actual |
|---|---|---|
| Filas | 1,551,437 | 337,250 |
| Estaciones | 411 | 469 |
| Valores faltantes | 0 | 0 |
| Filas duplicadas (estación y hora) | 0 | 0 |
| Columnas constantes | ninguna | ninguna |

## P2: entrenamiento contra julio-agosto 2026

- Referencia: 2026-01-08 a 2026-06-30, 1,551,437 filas.
- Actual: 2026-07-01 a 2026-08-31, 662,771 filas.
- Variables con drift: 2 de 12 (17%); conjunto con drift: **no**.

| Variable | Tipo | Prueba | Distancia | Umbral | Drift | Media ref. | Media actual |
|---|---|---|---|---|---|---|---|
| departures_lag_1 | numérica | Wasserstein distance (normed) | 0.0508 | 0.10 | no | 1.301 | 1.175 |
| departures_lag_24 | numérica | Wasserstein distance (normed) | 0.0496 | 0.10 | no | 1.300 | 1.178 |
| departures_lag_168 | numérica | Wasserstein distance (normed) | 0.0495 | 0.10 | no | 1.290 | 1.168 |
| departures_mean_24 | numérica | Wasserstein distance (normed) | 0.0924 | 0.10 | no | 1.299 | 1.177 |
| departures_mean_168 | numérica | Wasserstein distance (normed) | 0.1030 | 0.10 | sí | 1.298 | 1.177 |
| virtual_occupancy | numérica | Wasserstein distance (normed) | 0.0471 | 0.10 | no | 0.378 | 0.385 |
| net_flow_lag_1 | numérica | Wasserstein distance (normed) | 0.0455 | 0.10 | no | 0.000 | 0.000 |
| net_flow_lag_24 | numérica | Wasserstein distance (normed) | 0.0460 | 0.10 | no | 0.000 | 0.000 |
| station_id | categórica | Jensen-Shannon distance | 0.2266 | 0.10 | sí | - | - |
| hour | categórica | Jensen-Shannon distance | 0.0005 | 0.10 | no | - | - |
| weekday | categórica | Jensen-Shannon distance | 0.0161 | 0.10 | no | - | - |
| is_weekend | categórica | Jensen-Shannon distance | 0.0022 | 0.10 | no | - | - |

Estaciones del periodo actual ausentes de la referencia: 57, con 7.7% de sus filas.

| Calidad | Referencia | Actual |
|---|---|---|
| Filas | 1,551,437 | 662,771 |
| Estaciones | 411 | 468 |
| Valores faltantes | 0 | 0 |
| Filas duplicadas (estación y hora) | 0 | 0 |
| Columnas constantes | ninguna | ninguna |
