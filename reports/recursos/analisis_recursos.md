# Análisis de consumo de recursos — MiBici

**Entregable 7 — Punto 4: Monitoreo de recursos**  
**Proyecto:** MiBici — Equipo 45  
**Herramienta:** Docker Stats  
**Escenarios:** Baseline, carga y estrés (sin caché)

## 1. Objetivo

Analizar el consumo de CPU y memoria de los contenedores de la API de predicción y MLflow durante las pruebas de carga realizadas con Locust, identificando riesgos de capacidad y posibles oportunidades de optimización.

## 2. Metodología

Se utilizaron los registros de `docker stats` generados durante las pruebas de carga del proyecto MiBici.

Los escenarios analizados fueron:

| Escenario | Usuarios simulados | Duración |
|---|---:|---:|
| Baseline | 5 | 60 segundos |
| Carga | 25 | 120 segundos |
| Estrés | 100 | 120 segundos |

Los contenedores evaluados fueron:

- `mibici-equipo45-api-1`: API de predicción.
- `mibici-equipo45-mlflow-1`: servidor MLflow.

De acuerdo con `docker-compose.yml`, la API tiene configurado un límite de 2 CPU y 1 GiB de memoria, mientras que MLflow tiene un límite de 1 CPU y 1 GiB de memoria.

Los registros disponibles corresponden a capturas puntuales, por lo que no representan promedios, máximos ni percentiles de utilización durante toda la prueba.

## 3. Resultados de consumo

### 3.1. Utilización de CPU

| Escenario | API CPU | MLflow CPU |
|---|---:|---:|
| Baseline | 0.21 % | 1.08 % |
| Carga | 0.22 % | 0.83 % |
| Estrés | 0.17 % | 0.68 % |

Los porcentajes observados son bajos en las capturas disponibles. Sin embargo, estos valores no permiten concluir que la CPU estuvo subutilizada durante toda la prueba, debido a que no se dispone de una serie temporal de mediciones.

### 3.2. Consumo de memoria

| Escenario | API (MiB) | API (%) | MLflow (MiB) | MLflow (%) |
|---|---:|---:|---:|---:|
| Baseline | 830.6 | 81.12 % | 1010 | 98.59 % |
| Carga | 957.9 | 93.54 % | 1010 | 98.62 % |
| Estrés | 1009 | 98.52 % | 1009 | 98.56 % |

El consumo de memoria de la API aumenta conforme crece la carga simulada, pasando de 830.6 MiB a 1009 MiB.

MLflow mantiene una utilización cercana al límite configurado de 1 GiB en los tres escenarios.

Estos resultados muestran un margen de memoria reducido, especialmente durante las pruebas de carga y estrés.

### 3.3. Procesos y tareas (PIDS)

| Escenario | API PIDS | MLflow PIDS |
|---|---:|---:|
| Baseline | 39 | 108 |
| Carga | 58 | 102 |
| Estrés | 85 | 102 |

El número de procesos o tareas de la API aumenta con la carga, mientras que MLflow presenta valores relativamente estables.

Este comportamiento puede relacionarse con la concurrencia, aunque se requieren mediciones adicionales para determinar su causa.

## 4. Relación con el desempeño

Los resultados de Locust permiten complementar el análisis de recursos.

| Escenario | Usuarios | RPS global | p95 global | Errores |
|---|---:|---:|---:|---:|
| Baseline | 5 | 11.14 | 320 ms | 0 % |
| Carga | 25 | 51.79 | 680 ms | 0 % |
| Estrés | 100 | 97.50 | 590 ms | 0 % |

El criterio de aceptación documentado es p95 menor o igual a 500 ms y tasa de errores menor o igual al 1 %.

El escenario baseline cumple los criterios, mientras que carga y estrés no cumplen el límite de latencia.

El aumento de memoria y las degradaciones de latencia sugieren la necesidad de investigar restricciones de capacidad, pero no permiten atribuir causalidad a la memoria sin mediciones adicionales.

## 5. Riesgos identificados

### 5.1. Presión de memoria

La API alcanza 98.52 % de utilización durante estrés y MLflow permanece cerca de 99 %.

Esto representa un riesgo potencial de agotamiento de memoria si el consumo continúa aumentando.

### 5.2. Limitaciones del monitoreo

Las capturas puntuales no permiten identificar picos transitorios, duración de saturaciones ni correlación temporal entre utilización de recursos y latencia.

### 5.3. Capacidad operativa

Aunque las pruebas reportan 0 % de errores, los escenarios de carga y estrés incumplen el objetivo de latencia.

Por ello, la capacidad aceptable no debe definirse únicamente por el volumen de solicitudes procesadas.

## 6. Recomendaciones

1. Capturar métricas de CPU y memoria de forma periódica durante toda la ejecución de Locust.
2. Registrar máximos, promedios y percentiles de utilización.
3. Investigar el consumo elevado de memoria en MLflow y la API.
4. Comparar configuraciones con y sin caché bajo condiciones equivalentes.
5. Separar el monitoreo de solicitudes de salud, entradas inválidas e inferencias válidas.
6. Definir alertas preventivas de memoria y latencia.
7. Utilizar los resultados para dimensionar la infraestructura y elaborar el análisis FinOps del punto 5.

## 7. Conclusión

Las mediciones disponibles muestran un aumento de memoria en la API conforme crece la carga simulada y una utilización persistentemente elevada de memoria en MLflow.

El escenario de estrés alcanza aproximadamente 98.5 % del límite de memoria en ambos contenedores.

Las pruebas de carga y estrés también presentan latencias p95 superiores al objetivo de 500 ms.

Se recomienda ampliar la instrumentación y evaluar configuraciones alternativas antes de establecer la capacidad operativa definitiva.

Los registros actuales permiten identificar riesgos y formular recomendaciones, pero no demuestran por sí mismos un cuello de botella específico ni un fallo por falta de memoria.

## 8. Evidencia

- `reports/carga_sin_cache/baseline/docker_stats.txt`
- `reports/carga_sin_cache/carga/docker_stats.txt`
- `reports/carga_sin_cache/estres/docker_stats.txt`
- `reports/carga_sin_cache/baseline/resumen.md`
- `reports/carga_sin_cache/carga/resumen.md`
- `reports/carga_sin_cache/estres/resumen.md`
- `docker-compose.yml`

Este documento interpreta evidencia existente y no modifica los servicios ni los escenarios de prueba.
