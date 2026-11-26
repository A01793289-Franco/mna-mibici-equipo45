# Model Card — MiBici, Equipo 45

**Proyecto:** MiBici (Guadalajara) · **Equipo:** 45 · **Actividad:** Entrega final del proyecto integrador
**Fecha:** 26 de noviembre de 2026 · **Código base revalidado:** `d4bb784`
**Formato:** basado en *Model Cards for Model Reporting* (Mitchell et al., 2019).

Esta ficha documenta el modelo principal del proyecto, **P1 — demanda por estación**, y resume los otros dos modelos registrados (P2 y P3). Todas las cifras provienen de evidencias del repositorio; cada sección indica su fuente.

## 1. Detalles del modelo

| Elemento | P1 — demanda (principal) | P2 — riesgo | P3 — grupos |
|---|---|---|---|
| Modelo registrado | `mibici-p1-demanda` | `mibici-p2-riesgo` | `mibici-p3-grupos` |
| Tipo | Regresión de conteos | Clasificación de 3 clases | Clustering |
| Algoritmo del champion | `StationGrouper` + `HistGradientBoostingRegressor` (pérdida Poisson) | Regla de persistencia sobre la ocupación virtual actual | K-means, k = 3 |
| Hiperparámetros | `learning_rate=0.1`, `max_iter=100`, `max_leaf_nodes=31`, semilla 42 | Umbrales 10 % y 90 %; ocupación inicial 50 % | `n_init=10`, semilla 42 |
| Versión `@champion` | v1 (run `da28d047b8384d089de6f74fcd4e175d`) | v1 (run `fb52c91b260843a992fe74ecfac7201c`) | v1 (run `1079f92ad21d4f2cbc7dfa29c0d01253`) |
| Candidata en el registro A/B | v2: mismo algoritmo, reentrenado con enero–agosto | — | — |
| Criterio de selección | Menor `val_mae` | Mayor `val_f1_macro` | Mayor `val_ari` (estabilidad entre periodos) |
| Servido en la API | Sí: `POST /predict/p1` | Sí: `POST /predict/p2` | No: análisis por lotes |

- **Linaje:** cada versión guarda en MLflow el `run_id`, el experimento, el `git_commit`, `data_version` (`5ca52ccee062…`), `feature_version` (`87c1e6136a5f…`), sus parámetros efectivos, la firma del modelo, ejemplos de entrada y `config/model_check.json` para comprobar sus predicciones al recuperarlo.
- **Código:** entrenamiento en `mibici/train.py`, predicción en `mibici/predict.py`, recuperación por alias en `mibici/model_loader.py` y verificación del Registry en `mibici/verify_registry.py`. Se ejecuta como MLflow Project (`MLproject`).
- **Serialización:** `skops`.
- **Licencia del código:** MIT (`LICENSE`). La licencia no aplica a los datos (sección 4).

El 26 de noviembre se recuperaron los tres champion reales y se reprodujeron sus
predicciones y métricas. El registro local de referencia contiene P1/P2/P3 v1. El registro
separado de la reproducción A/B contiene P1 v1/v2, con otros run IDs. Los números de
versión se interpretan dentro de su registro, no como identificadores universales.
[Consulta de linaje y aliases](evidencias_20261126/registry_linaje.json).

Fuentes: [resultados de la segunda entrega](../resultados_mlflow_entrega2.md), [integración del Registry](../../references/integracion_registry.md) y [validación del Registry](validacion_registry.md).

## 2. Uso previsto

| Pregunta | Decisión que apoya | Usuario previsto |
|---|---|---|
| P1 | Cuántas bicicletas disponer por estación en la siguiente hora | Operación y logística de MiBici |
| P2 | Qué estaciones revisar y priorizar para rebalanceo | Equipo de rebalanceo |
| P3 | Qué estaciones comparten patrones de uso y dónde se ubican | Planeación de la red |

- **Inferencia:** P1 y P2 predicen cada hora y solo usan eventos anteriores al momento de la predicción. P3 se actualiza por lotes; se propone hacerlo una vez al mes.
- **Fuera de alcance:**
  - Decisiones sobre personas usuarias. El modelo trabaja con agregados por estación y hora.
  - Tratar P2 como inventario real. Predice un **estado virtual** derivado de viajes, no la disponibilidad medida por el operador.
  - Horizontes mayores a una hora, otras ciudades u otros sistemas de bicicletas sin reentrenar ni validar.
  - Sustituir automáticamente el champion a partir de una alerta de drift.

## 3. Factores relevantes

- **Estación.** El champion de P1 conserva 254 categorías de estación, las más frecuentes por número de filas. Las demás estaciones y las nuevas caen en "otras" y se predicen sin un efecto propio de la estación. En septiembre, el 46.0 % de las filas cayó en "otras" y el 12.2 % correspondía a estaciones que no estaban en el entrenamiento.
- **Calendario.** La demanda depende de la hora, del día de la semana y de si es fin de semana.
- **Capacidad de la estación.** P2 depende de la capacidad del catálogo `nomenclatura_2026_09.csv`, que se tomó como fija para todo el periodo.

## 4. Datos

| Elemento | Valor |
|---|---|
| Fuente | CSV mensuales de viajes abiertos de MiBici, enero–septiembre de 2026, y el catálogo de estaciones |
| Volumen | 3,358,273 viajes válidos; 471 estaciones observadas |
| Entrenamiento | 1 de enero al 30 de junio de 2026 (1,552,105 filas estación-hora en P1) |
| Validación | Julio–agosto de 2026 (665,747 filas en P1) |
| Prueba retrospectiva | Septiembre de 2026 (338,690 filas en P1) |
| Trazabilidad | `references/data_manifest.json` (URL, SHA-256 y conteos) y `references/feature_manifest.json` |

**Variables:**
- **P1:** hora, día de la semana, fin de semana, mes, rezagos de 1, 24 y 168 h, medias de 24 y 168 h, y estación.
- **P2:** las de P1 sin la estación, más ocupación virtual y flujo neto con rezagos de 1 y 24 h.
- **P3:** 48 medias horarias normalizadas, separadas en día laborable y fin de semana. Las coordenadas solo se usan para el mapa.

Se excluyen los horizontes que cruzan los cortes entre particiones, así como las primeras 168 horas porque no tienen historia suficiente.

Las cifras de entrenamiento y evaluación describen la versión histórica usada por estos
modelos. La ejecución nueva del MLflow Project conserva su propia versión de datos y
características. El código actual descubre el catálogo publicado si el proveedor retira
el anterior; ese cambio no altera los manifiestos históricos ni acredita una reproducción
exacta. La [revalidación final](revalidacion_20261126.md) distingue ambas ejecuciones.

**Privacidad y condiciones de uso:**
- Los modelos no usan identificadores de personas, edad, género ni otros atributos personales. El ID del viaje solo se usa para eliminar duplicados.
- No se identificó una licencia específica para redistribuir los CSV, así que el repositorio publica solo agregados y manifiestos, no los archivos por viaje.

Fuentes: [ML Canvas](../../references/ml_canvas.md), [propuesta](../../references/propuesta.md) y [condiciones de datos](../../references/condiciones_datos.md).

## 5. Métricas y desempeño

### 5.1 P1 — demanda (champion v1)

| Conjunto | MAE | RMSE | WAPE | R² |
|---|---:|---:|---:|---:|
| Validación (julio–agosto) | 0.7498 | 1.4446 | 64.03 % | 0.6256 |
| Septiembre (retrospectivo) | 0.8620 | 1.6683 | 59.71 % | 0.6425 |

En validación, el champion mejora al baseline estacional (la semana anterior), cuyo MAE es 0.8988: el error baja 16.6 %. El MAE se mide en viajes por estación y hora.

### 5.2 P1 — comparación A/B offline (v1 contra v2)

| Métrica en septiembre | v1 `@champion` | v2 `@challenger` |
|---|---:|---:|
| MAE | 0.8620 | 0.8577 |
| RMSE | 1.6683 | 1.6111 |
| WAPE | 59.71 % | 59.41 % |
| R² | 0.6425 | 0.6666 |
| MAE en estaciones nuevas (58) | 0.4728 | 0.4696 |

- La v2 reduce el MAE en 0.004321, con un IC del 95 % de [0.002236, 0.006238]. El intervalo se obtuvo con bootstrap pareado circular: bloques de 7 días, 5,000 réplicas y semilla 42.
- La v2 cumple los cuatro criterios definidos: MAE menor, IC favorable, RMSE sin empeorar y estaciones nuevas sin empeorar.
- La comparación es offline y retrospectiva y **no modifica ningún alias**.

Fuente: [resultados del A/B](../abtest/resultados.md).

### 5.3 P2 — riesgo (champion v1, regla de persistencia)

| Conjunto | F1 macro | Balanced accuracy | AP macro |
|---|---:|---:|---:|
| Validación | 0.8824 | 0.8824 | 0.8130 |
| Septiembre (retrospectivo) | 0.8695 | 0.8695 | 0.7929 |

| Clase (validación) | Precisión | Recall |
|---|---:|---:|
| Normal | 0.9154 | 0.9154 |
| Riesgo sin bicicletas | 0.8877 | 0.8879 |
| Riesgo sin anclajes | 0.8439 | 0.8439 |

- La regla de persistencia superó en F1 macro al gradient boosting ajustado (0.8723) y a la regresión logística (0.8223), y además cuesta menos.
- Sus salidas son 0/1, no probabilidades calibradas, por lo que la AP de esta regla debe interpretarse con cautela.

### 5.4 P3 — grupos (champion v1, K-means k = 3)

| Métrica | Valor |
|---|---:|
| Silhouette (entrenamiento) | 0.1407 |
| Davies-Bouldin (entrenamiento) | 1.9784 |
| ARI de estabilidad entre periodos | 0.5776 |
| Tamaños de los grupos | 213 / 33 / 151 estaciones |

El ARI mide si los grupos se mantienen entre periodos. No es una exactitud supervisada. El silhouette bajo indica que la separación entre grupos es limitada.

## 6. Despliegue y operación

- **Servicio:** FastAPI contenerizada (`Containerfile`), orquestada con Docker Compose junto con MLflow y un servicio que importa y verifica los modelos del Registry. La API carga los modelos por alias `@champion`, así que cambiar de versión no requiere reconstruir la imagen.
- **CI/CD:** GitHub Actions ejecuta pruebas en Ubuntu y Windows, revisiones de seguridad, construcción de la imagen, despliegue temporal con Compose y verificación HTTP. Fuente: [evidencia de CI](evidencia_validacion_ci.md).
- **Carga con Locust:** revalidación del 26 de noviembre con los modelos reales, Docker
  Desktop 29.8.0 en Linux, Intel Core Ultra 9 285K y VM de 24 CPU / 8 GiB. La API tiene
  límites de 2 CPU / 1 GiB. Locust corre en el mismo anfitrión. Criterios definidos por
  el equipo: p95 ≤ 500 ms y errores ≤ 1 %.

  | Escenario | Usuarios | RPS totales | p95 | Errores |
  |---|---:|---:|---:|---:|
  | Baseline | 5 | 15.79 | 8 ms | 0 % |
  | Estrés | 100 | 280.08 | 200 ms | 0 % |

  Fuente: [resumen de la revalidación](evidencias_20261126/locust/resumen.md). Son dos
  corridas de 60 y 120 s. Los RPS incluyen health y rechazos 422 esperados; en estrés
  P1/P2 suman 224.03 predicciones válidas/s. Esta campaña se conserva separada de la
  campaña Podman/WSL2 del 21 de noviembre y de las pruebas Docker del 20 de noviembre.
  MLflow alcanzó 376.6 MiB de memoria durante el estrés, después de desactivar los
  trabajos en segundo plano. No es una prueba prolongada ni determina capacidad de EC2.

- **Costos (FinOps):**
  - Como referencia de cómputo Linux On-Demand, una AWS c6i.xlarge cuesta USD 124.10 por 730 horas en us-east-1 y USD 130.31 en mx-central-1. Las tarifas se confirmaron el 26 de noviembre; no hubo despliegue ni facturación en AWS.
  - Con la demanda estimada (480 estaciones × 24 h × 2 modelos ≈ 23,040 inferencias diarias), el costo efectivo es de USD 0.18 a 0.19 por cada 1,000 inferencias.
  - La tarifa base de t3.large reduce aproximadamente 51 % del cómputo. Su adopción requiere medir su capacidad y créditos de CPU; este porcentaje no estima la factura total.
  - El cálculo excluye almacenamiento, red, IP pública, balanceador e impuestos. El rendimiento medido localmente no garantiza capacidad equivalente en EC2.

  Fuente: [análisis FinOps](../finops/analisis_costos.md).

## 7. Monitoreo

- **Drift con Evidently:** compara el periodo de entrenamiento contra julio–agosto y contra septiembre. El umbral es 0.1 para la distancia de Wasserstein normalizada (variables numéricas) y para Jensen-Shannon (categóricas).
- **Resultados:**
  - Ningún conjunto presenta drift global.
  - `station_id` sí presenta drift en septiembre: 0.2620 en P1 y 0.2605 en P2, con 58 estaciones ausentes del entrenamiento.
  - `departures_mean_168` presenta drift leve solo en julio–agosto: 0.1052 en P1 y 0.1030 en P2.
- **Calidad de datos:** no hay valores faltantes, filas duplicadas por estación y hora ni columnas constantes.
- **Política:**
  - Revisar mensualmente.
  - Un drift abre una revisión técnica pero **no** cambia el champion por sí solo.
  - Una versión nueva se promueve solo con evidencia favorable en un periodo posterior, y se conserva la anterior para poder revertir.

Fuentes: [resumen de drift](../evidently/resumen.md) e [interpretación](../evidently/interpretacion_drift.md).

## 8. Consideraciones éticas

- **Privacidad:** se trabaja solo con agregados por estación y hora, sin atributos personales.
- **Equidad territorial:** las estaciones nuevas o poco frecuentes reciben predicciones genéricas en P1. Si el rebalanceo se guiara solo por el modelo, podría favorecer a las zonas con más historial. Por eso se recomienda revisar los errores por estación antes de asignar recursos.
- **Impacto operativo:** un falso "normal" en P2 puede dejar una estación sin bicicletas o sin anclajes. El modelo es una herramienta de apoyo; la decisión final es del equipo de operación.
- **Datos:** antes de redistribuir los CSV o darles un uso comercial, hay que confirmar la autorización con el proveedor.

## 9. Limitaciones y advertencias

1. Septiembre ya se había observado en entregas anteriores, así que su evaluación es **retrospectiva** y no una prueba independiente nueva. La selección de modelos se hizo solo con validación.
2. P2 evalúa un **inventario virtual**: arranca al 50 % de la capacidad y acumula llegadas menos salidas. No reproduce el rebalanceo real del operador.
3. El catálogo de estaciones es posterior al periodo y se trató como fijo para todos los meses, lo que es una limitación retrospectiva.
4. El notebook `2.0-analisis-errores-p1.ipynb` desglosa los errores de validación por hora, decil de demanda y estación. La comparación A/B resume estaciones conocidas y nuevas; estos análisis no constituyen una auditoría formal de equidad territorial.
5. El A/B se hizo offline, sin asignar tráfico real de forma aleatoria. Sus resultados no garantizan el mismo desempeño en meses futuros.
6. Los tiempos de entrenamiento e inferencia se midieron en una sola máquina y una sola ejecución.

## 10. Estado de operación y decisión de entrega

| Pregunta | Champion | Challenger | Decisión vigente |
|---|---|---|---|
| P1 | v1 en el registro de referencia | v2 en el registro separado de A/B | La API de entrega mantiene v1; v2 conserva la recomendación experimental |
| P2 | v1 | — | Persistencia del proxy, elegida por F1 macro y menor costo |
| P3 | v1 | — | K-means k = 3, por lotes |

Los aliases y el linaje se consultaron en las copias locales de los registros reales del
equipo; los cuatro smoke tests y la reproducción de métricas aprobaron. El servicio
Compose importa P1/P2 y comprueba sus predicciones antes de exponer la API. La asignación
`champion` define el estado de consumo de este prototipo local y no un servicio público
en producción. No se declara acceso al servidor privado de otro integrante.

La decisión conserva v1 para la entrega y limita la promoción de v2 a una evaluación en
otro periodo y revisión técnica. La ventaja retrospectiva observada no demuestra por sí
sola desempeño futuro. El protocolo conserva el modelo anterior para reversión y evita
promover automáticamente por drift. Evidencia: [revalidación final](revalidacion_20261126.md).

## Referencias

Mitchell, M., Wu, S., Zaldivar, A., Barnes, P., Vasserman, L., Hutchinson, B., Spitzer, E., Raji, I. D. y Gebru, T. (2019). Model Cards for Model Reporting. *Proceedings of the Conference on Fairness, Accountability, and Transparency*, 220–229. https://doi.org/10.1145/3287560.3287596
