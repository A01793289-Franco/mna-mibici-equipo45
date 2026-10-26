# Resultados reales | Equipo 45

Commit de ejecución de la primera iteración (tablas P1, P2 y P3 siguientes y evaluación de septiembre): `43bf339792fef5d01326aa0ca0227fdd781675ff`. Las secciones posteriores a "Interpretación" corresponden a la segunda iteración; su trazabilidad se describe al final.

## P1

| Run | val_mae | val_rmse | val_wape | val_r2 | test_mae | test_rmse | test_wape | test_r2 |
|---|---|---|---|---|---|---|---|---|
| P1_estacional_h1 | 0.898799 | 1.818495 | 0.767592 | 0.406735 | 1.026387 | 2.107478 | 0.710894 | 0.429568 |
| P1_hgb_poisson_h1 | 0.761427 | 1.436289 | 0.650273 | 0.629909 | 0.871903 | 1.634484 | 0.603896 | 0.656886 |

## P2

| Run | val_f1_macro | val_balanced_accuracy | val_ap_macro | test_f1_macro | test_balanced_accuracy | test_ap_macro |
|---|---|---|---|---|---|---|
| P2_logistica_proxy_h1 | 0.822339 | 0.885572 | 0.903375 | 0.811433 | 0.879905 | 0.884816 |
| P2_hgb_proxy_h1 | 0.870816 | 0.908473 | 0.955667 | 0.857368 | 0.900603 | 0.946310 |

## P3

| Run | train_silhouette | train_davies_bouldin | val_ari |
|---|---|---|---|
| P3_kmeans_perfil48 | 0.140695 | 1.978430 | 0.577564 |
| P3_ward_perfil48 | 0.123216 | 2.138794 | 0.311556 |

## Interpretación

En validación, P1 reduce MAE de 0.8988 a 0.7614. En la evaluación única de septiembre reduce MAE de 1.0264 a 0.8719 (aproximadamente 15.1%). Este último valor representa el error absoluto medio de viajes por estación-hora. El WAPE de 60.39% sigue siendo elevado y no debe interpretarse como exactitud; requiere analizar errores por estación y nivel de demanda.

P2 mejora F1 macro de validación de 0.8223 a 0.8708 y de prueba de 0.8114 a 0.8574. En el candidato, la clase de riesgo sin anclajes tiene recall de prueba de 0.9363, pero precisión de 0.6987: aún genera falsas alarmas. Las etiquetas proceden de una simulación con ocupación inicial de 50%, sin inventarios observados ni rebalanceos. Las métricas muestran concordancia con ese proxy y no validan disponibilidad física ni decisiones automáticas. El escenario evaluado utiliza un estado inicial de 50%.

P3 favorece K-means frente a Ward en las tres métricas. K-means produce grupos de 213, 33 y 151 estaciones, con 397 estaciones comunes al comparar periodos. El ARI de 0.5776 indica estabilidad parcial, no coincidencia perfecta; silhouette de 0.1407 advierte superposición. Tres grupos fue una decisión inicial fijada antes del experimento y el barrido de k (sección siguiente) la respalda. No se evaluó P3 sobre septiembre.

En la primera iteración, los tres candidatos se comparan solo con su baseline dentro de cada pregunta. La semilla 42 y las seis configuraciones se fijaron antes de la prueba; la primera iteración no realizó búsqueda de hiperparámetros (la segunda se describe más abajo). Por tanto, no se atribuye causalmente la mejora a un único hiperparámetro.

## Control de rigor en P2: baseline de persistencia

La etiqueta de P2 es la clase de la ocupación virtual una hora después, y la ocupación virtual actual es uno de los predictores. Por eso se agregó `P2_persistencia_proxy_h1`, una regla sin aprendizaje que predice que la clase no cambia (sin bicicletas si `virtual_occupancy <= 0.10`, sin anclajes si `>= 0.90`, normal en otro caso). Se evaluó solo en validación; no se calculó para septiembre, porque esa evaluación ya se usó una vez.

| Run | val_f1_macro | val_balanced_accuracy | precisión / recall sin bicicletas | precisión / recall sin anclajes |
|---|---|---|---|---|
| P2_persistencia_proxy_h1 | 0.882361 | 0.882362 | 0.8877 / 0.8879 | 0.8439 / 0.8439 |
| P2_logistica_proxy_h1 | 0.822339 | 0.885572 | 0.7765 / 0.9394 | 0.6436 / 0.9502 |
| P2_hgb_proxy_h1 | 0.870816 | 0.908473 | 0.8622 / 0.9193 | 0.7264 / 0.9461 |

La regla de persistencia supera al boosting en F1 macro de validación (0.8824 contra 0.8708), la métrica principal del proyecto. El boosting no aporta una mejora clara en esa métrica. La diferencia que sí existe es de tipo de error: el boosting tiene mayor balanced accuracy (0.9085 contra 0.8824) y recall más alto en las dos clases de riesgo (0.919 y 0.946 contra 0.888 y 0.844), a cambio de menor precisión, sobre todo en riesgo sin anclajes (0.726 contra 0.844). Es decir, detecta más situaciones de riesgo pero con más falsas alarmas. La AP macro de la regla (0.813) no es comparable con la de los modelos, porque sus probabilidades son 0 o 1.

Este resultado es coherente con la advertencia del diseño: la etiqueta y el predictor salen de la misma simulación y el estado cambia poco de una hora a la siguiente, así que la métrica mide sobre todo concordancia con el proxy. La mejora de P2 sobre sus baselines de aprendizaje (logística) es real, pero no demuestra que el boosting aprenda dinámica de disponibilidad más allá de la persistencia. Para decidir cuál usar importa más qué error cuesta más: si es perderse un riesgo (recall), conviene el boosting; si son las falsas alarmas (precisión), conviene la regla.

## Ajuste de hiperparámetros (segunda iteración)

La primera iteración usó los valores por defecto de scikit-learn y no buscó hiperparámetros. Esta segunda iteración se ejecuta con `python -m mibici.train --question all --tune`. Para que no tarde horas, cada combinación se entrena con una muestra aleatoria de 300,000 filas del entrenamiento (de 1,552,105 en P1; semilla 42) y se mide en toda la validación de julio-agosto. No se usó validación cruzada aleatoria ni septiembre: los 24 runs hijo no registran métricas `test_`. La cuadrícula (6 a 12 combinaciones) tiene 12: `learning_rate` en {0.05, 0.1}, `max_leaf_nodes` en {15, 31, 63} y `max_iter` en {100, 300}, que incluye los valores por defecto (0.1, 31, 100). La combinación ganadora se reentrena con todo el entrenamiento y se registra como un candidato adicional.

**P1: `val_mae` por combinación** (run padre `P1_busqueda_hgb_h1`)

| learning_rate | max_leaf_nodes | max_iter | val_mae | val_wape |
|---|---|---|---|---|
| 0.05 | 15 | 100 | 0.7758 | 0.6626 |
| 0.05 | 15 | 300 | 0.7613 | 0.6502 |
| 0.05 | 31 | 100 | 0.7664 | 0.6545 |
| 0.05 | 31 | 300 | 0.7587 | 0.6479 |
| 0.05 | 63 | 100 | 0.7632 | 0.6518 |
| 0.05 | 63 | 300 | 0.7577 | 0.6471 |
| 0.1 | 15 | 100 | 0.7690 | 0.6567 |
| 0.1 | 15 | 300 | 0.7610 | 0.6499 |
| 0.1 | 31 | 100 | 0.7651 | 0.6534 |
| 0.1 | 31 | 300 | 0.7618 | 0.6506 |
| 0.1 | 63 | 100 | 0.7624 | 0.6511 |
| 0.1 | 63 | 300 | 0.7621 | 0.6509 |

**P2: `val_f1_macro` por combinación** (run padre `P2_busqueda_hgb_h1`)

| learning_rate | max_leaf_nodes | max_iter | val_f1_macro | val_balanced_accuracy |
|---|---|---|---|---|
| 0.05 | 15 | 100 | 0.8712 | 0.9069 |
| 0.05 | 15 | 300 | 0.8734 | 0.9076 |
| 0.05 | 31 | 100 | 0.8718 | 0.9073 |
| 0.05 | 31 | 300 | 0.8738 | 0.9075 |
| 0.05 | 63 | 100 | 0.8730 | 0.9074 |
| 0.05 | 63 | 300 | 0.8739 | 0.9072 |
| 0.1 | 15 | 100 | 0.8728 | 0.9074 |
| 0.1 | 15 | 300 | 0.8735 | 0.9072 |
| 0.1 | 31 | 100 | 0.8727 | 0.9075 |
| 0.1 | 31 | 300 | 0.8727 | 0.9075 |
| 0.1 | 63 | 100 | 0.8736 | 0.9073 |
| 0.1 | 63 | 300 | 0.8736 | 0.9073 |

| Run (entrenamiento completo, validación) | Combinación | Métrica principal | Defecto |
|---|---|---|---|
| P1_hgb_poisson_ajustado_h1 | 0.05, 63, 300 | val_mae 0.7552 (WAPE 0.6450, R² 0.6676) | 0.7614 (WAPE 0.6503, R² 0.6299) |
| P2_hgb_ajustado_proxy_h1 | 0.05, 63, 300 | val_f1_macro 0.8723 (balanced accuracy 0.9091) | 0.8708 (0.9085) |

**Interpretación.** El ajuste aporta poco. En P1 el MAE de validación baja de 0.7614 a 0.7552 (cerca de 0.8%), y en la cuadrícula los valores van de 0.7577 a 0.7758: las combinaciones con 100 iteraciones y pocas hojas son las peores, y a partir de 300 iteraciones las diferencias son de milésimas. En P2 todas las combinaciones quedan entre 0.8712 y 0.8739 de F1 macro, una diferencia que no se puede distinguir de la variación entre muestras; el modelo ajustado (0.8723) sigue por debajo de la regla de persistencia (0.8824), así que la conclusión de la sección anterior no cambia. Conclusión práctica: los valores por defecto ya estaban cerca de lo mejor que ofrece esta cuadrícula, y el límite de P2 viene del proxy y no de los hiperparámetros. La mejor combinación está en el borde de la cuadrícula (menor tasa de aprendizaje, más hojas y más iteraciones), por lo que una exploración más amplia podría mejorar P1 un poco más; no se hizo para no seguir optimizando sobre la validación.

La cifra de septiembre (MAE 0.8719 en P1, F1 macro 0.8574 en P2) corresponde a la configuración por defecto y queda como valor histórico de la primera iteración. Los modelos ajustados se comparan en validación y no se evaluaron en septiembre.

## Barrido del número de grupos en P3

Hasta aquí k=3 era una decisión fijada antes del experimento. El run `P3_barrido_k_perfil48` la contrasta: entrena K-means y Ward con k de 2 a 8 sobre los perfiles de 397 estaciones y registra, para cada k, la silhouette y el índice de Davies-Bouldin en entrenamiento y el ARI entre la agrupación de entrenamiento y la de validación en las estaciones comunes. Usa solo `p3_train` y `p3_val`; no se abrió `p3_test.parquet`. La figura `reports/figures/p3_barrido_k_perfil48.png` muestra las tres métricas contra k, y la tabla completa se reproduce abajo y queda como artefacto del run (carpeta `tablas`).

**K-means**

| k | silhouette | Davies-Bouldin | ARI entre periodos | grupo más pequeño |
|---|---|---|---|---|
| 2 | 0.1325 | 2.4464 | 0.4578 | 167 |
| 3 | 0.1407 | 1.9784 | 0.5776 | 33 |
| 4 | 0.1131 | 2.0854 | 0.3726 | 27 |
| 5 | 0.1165 | 2.1077 | 0.2923 | 27 |
| 6 | 0.0963 | 2.1409 | 0.3728 | 20 |
| 7 | 0.0744 | 2.1223 | 0.2734 | 7 |
| 8 | 0.0717 | 2.0878 | 0.3384 | 5 |

**Ward**

| k | silhouette | Davies-Bouldin | ARI entre periodos | grupo más pequeño |
|---|---|---|---|---|
| 2 | 0.1040 | 2.5708 | 0.1390 | 149 |
| 3 | 0.1232 | 2.1388 | 0.3116 | 31 |
| 4 | 0.0688 | 2.4207 | 0.1760 | 31 |
| 5 | 0.0755 | 2.3748 | 0.1530 | 31 |
| 6 | 0.0788 | 2.1728 | 0.1518 | 4 |
| 7 | 0.0838 | 2.0835 | 0.1526 | 4 |
| 8 | 0.0671 | 2.1691 | 0.1831 | 4 |

**Justificación de k=3.** Con K-means, k=3 tiene la mayor silhouette (0.1407), el menor Davies-Bouldin (1.9784) y, con mucha ventaja, el mayor ARI entre periodos (0.5776; el siguiente es 0.4578 con k=2). Con Ward también tiene la mayor silhouette (0.1232) y el mayor ARI (0.3116), y su Davies-Bouldin (2.1388) es algo mayor que el mejor (2.0835 con k=7). Para k mayores aparecen grupos de 4 a 7 estaciones (k=7 y 8 en K-means; k≥6 en Ward), que no son interpretables, y la estabilidad entre periodos baja. Los tres criterios coinciden, así que el barrido respalda k=3 y no se cambió.

**Interpretación de los perfiles (K-means, perfil horario normalizado).** Con k=2 la separación es entre estaciones de pico matutino (picos a las 7 y 8 h en día laborable; 167 estaciones) y de pico vespertino (17 y 18 h; 230). Con k=3 el grupo vespertino se divide y aparece un grupo pequeño (33 estaciones) cuyo perfil pesa más en fin de semana (alrededor de 56% de su perfil, contra 39% en los otros dos), con un pico de fin de semana a las 11 y 12 h, y está algo más al sur que los demás. Con k=4 se divide el grupo vespertino en dos que difieren sobre todo en la intensidad de la punta de la tarde (42% contra 31% de sus salidas entre 16 y 19 h), lo que añade matiz pero baja silhouette y ARI. Por eso k=3 distingue tres usos con sentido: matutino, vespertino y fin de semana.

**Límite.** La silhouette sigue siendo baja en todos los k (máximo 0.14): los perfiles forman un continuo y los grupos se superponen. k=3 es la opción mejor respaldada entre las probadas, no una separación nítida. El ARI de 0.58 indica estabilidad parcial entre periodos.

## P1 con la estación como variable categórica

El candidato por defecto solo distingue estaciones por sus rezagos. `P1_hgb_poisson_estacion_h1` agrega `station_id` como variable categórica: cada una de las 254 estaciones con más horas de datos en entrenamiento tiene su propia categoría y el resto de las estaciones, junto con cualquier estación que no esté en entrenamiento, comparten la categoría "otras" (255 categorías en total, el máximo del boosting). La agrupación se aprende solo con el entrenamiento, es parte del modelo guardado (`StationGrouper` en `mibici/stations.py`) y las pruebas comprueban que una estación nueva no hace fallar la predicción. Los hiperparámetros son los de la configuración por defecto, para comparar solo el efecto de la estación.

| Run (validación) | val_mae | val_rmse | val_wape | val_r2 |
|---|---|---|---|---|
| P1_estacional_h1 | 0.8988 | 1.8185 | 0.7676 | 0.4067 |
| P1_hgb_poisson_h1 | 0.7614 | 1.4363 | 0.6503 | 0.6299 |
| P1_hgb_poisson_estacion_h1 | 0.7498 | 1.4446 | 0.6403 | 0.6256 |

Con la estación el MAE baja de 0.7614 a 0.7498 (cerca de 1.5%) y el WAPE de 0.6503 a 0.6403; es una mejora mayor que la del ajuste de hiperparámetros (0.7552), obtenida sin ajustar nada. A cambio, el RMSE sube de 1.4363 a 1.4446 y el R² baja de 0.6299 a 0.6256: el modelo acierta un poco mejor en los errores típicos, pero no mejora, e incluso empeora un poco, en los errores grandes. La ganancia es modesta.

La cobertura limita el efecto. En entrenamiento hay 413 estaciones: 254 tienen categoría propia y 159 quedan en "otras". En validación hay 470 estaciones, 57 de ellas sin ningún dato de entrenamiento, y 287,795 de las 665,747 filas de validación (43%) caen en "otras", donde el modelo no distingue estación. Por regla de elección (menor `val_mae`) este modelo queda como `champion` de P1. La mejora justifica conservarlo, porque el costo es una pieza adicional y pequeña, pero no es una mejora grande, y habría que probar si combinarlo con los hiperparámetros ajustados o con otra codificación (por ejemplo un promedio por estación calculado solo con entrenamiento) mejora más. No se evaluó en septiembre.

## Análisis de errores de P1

El detalle está en el cuaderno [2.0-analisis-errores-p1.ipynb](../notebooks/2.0-analisis-errores-p1.ipynb), que carga el modelo `champion` de `mibici-p1-demanda` y usa solo validación. Las figuras `reports/figures/p1_errores_hora.png` y `reports/figures/p1_errores_decil.png` resumen el error por hora y por decil de demanda reciente.

El error absoluto sigue a la demanda: las horas pico (7 a 9 h y 17 a 19 h) son 6 de las 24 horas y reúnen 38% del error absoluto total, y el decil de mayor demanda reciente concentra 23%. En términos relativos ocurre lo contrario: el WAPE baja de 1.61 en el decil de menor demanda a 0.43 en el de mayor, y de 1.2 a 1.4 en la madrugada y la noche a 0.54 a 0.58 en las horas pico; por eso el WAPE global de 64% proviene sobre todo de estaciones-hora con pocas salidas, donde el conteo tiene mucha variación aleatoria (hipótesis razonable, no medida aquí). El sesgo medio es casi nulo (-0.003; entre -0.017 y 0.022 por decil), con una ligera subestimación a las 18 h (0.073) y en el decil más alto. El error no está concentrado en pocas estaciones: las 10 con mayor error suman 7.9% del total y las 50 primeras, 24.9%; son estaciones grandes del centro cuyo WAPE (0.39) es menor que el del resto (0.68), de modo que fallan por tamaño y no por ser difíciles. Como siguiente paso conviene probar variables de feriados, eventos y clima si hay una fuente reproducible, complementar el WAPE con una métrica adecuada para conteos pequeños (como la desviación de Poisson) y revisar la subestimación de las 18 h.

## Sensibilidad de P2 a la ocupación inicial

La etiqueta de P2 depende de una ocupación virtual que parte de 50% de la capacidad, un supuesto sin respaldo en datos. `python -m mibici.sensitivity` repitió P2 con 25% y 75% (solo validación; figura `reports/figures/sensibilidad/p2_sensibilidad_ocupacion_inicial.png`).

| Ocupación inicial | Persistencia F1 macro | Logística F1 macro | Boosting F1 macro | Boosting exactitud balanceada | Clase normal (entrenamiento) | Sin bicicletas | Sin anclajes | Eventos recortados |
|---|---|---|---|---|---|---|---|---|
| 25% | 0.8821 | 0.8226 | 0.8703 | 0.9084 | 53.5% | 33.7% | 12.8% | 447,988 |
| 50% | 0.8824 | 0.8223 | 0.8708 | 0.9085 | 53.5% | 33.6% | 12.9% | 447,278 |
| 75% | 0.8829 | 0.8215 | 0.8709 | 0.9085 | 53.7% | 33.4% | 12.9% | 447,283 |

El resultado es estable: entre 25% y 75% el F1 macro cambia 0.0008 en la regla de persistencia, 0.0011 en la logística y 0.0006 en el boosting, y el orden de los modelos no cambia (la persistencia sigue por encima del boosting, y este de la logística). Las proporciones de clase varían menos de 0.4 puntos porcentuales en entrenamiento. Por lo tanto, las conclusiones de P2 no dependen del valor inicial elegido.

Una explicación probable (no medida aparte aquí) es que la ocupación se recorta a [0, 1] en cada evento y el diagnóstico de `p2_features` cuenta unos 447 mil eventos recortados en los tres escenarios. Cada recorte reinicia el estado en un extremo, de modo que el efecto del valor inicial se borra pronto. Eso hace al proxy poco sensible al supuesto inicial, pero también significa que la etiqueta depende más de la dinámica de recortes que de un inventario real. No sustituye datos observados de disponibilidad: la estabilidad frente a este supuesto no valida el proxy frente a la realidad. Septiembre no se usó.

## Trazabilidad y evidencia

**Primera iteración.** Los seis runs finalizaron y registran `git_dirty=false`, el mismo commit (`43bf339`), las mismas versiones de datos y variables, parámetros del estimador, etiquetas y al menos una figura. Las capturas auténticas de la interfaz están en `reports/figures/mlflow_*.png`; el JSON `resultados_mlflow.json` conserva sus métricas y parámetros con precisión completa.

**Segunda iteración.** El código y las cifras de cada análisis entraron en estos commits:

| Commit | Contenido |
|---|---|
| `13a97f9` | Modelos guardados con firma, Model Registry con `champion` y `predict.py` |
| `233d608` | Baseline de persistencia en P2 y búsqueda de hiperparámetros (`--tune`) |
| `e4d5e9d` | Barrido de k en P3 |
| `a4d5ac2` | Estación como variable categórica en P1 |
| `e0dc21a` | Análisis de errores de P1 |
| `f0acc9b` | Sensibilidad de P2 a la ocupación inicial |

**Reproducción histórica de las mejoras en Windows.** El 25 de octubre de 2026, entre las 19:24 y las 19:29, se ejecutaron `python -m mibici.train --question all --tune` y `python -m mibici.sensitivity` en Windows con Python 3.13.16. Los runs registran `git_commit=f0acc9b` y **`git_dirty=true`**: el árbol de trabajo tenía cambios sin confirmar, que se confirmaron a las 19:32 en `b95118a`.

Esos cambios eran solo documentales, más la fijación de `skops==0.16.0`, que es la versión ya instalada. Entre `f0acc9b` y `b95118a` no cambió ningún archivo `.py`, ninguna prueba ni ningún manifiesto; se puede comprobar con `git diff f0acc9b b95118a -- "*.py" tests/ references/*.json`, que no muestra diferencias. Por tanto, el código ejecutado es el de `f0acc9b`. Todos los runs registran `data_version` `6aeb2eeb…` y `feature_version` `7bf69341…`, las de los manifiestos usados en esa ejecución. Las métricas de validación coinciden con las publicadas en este documento, y las figuras de la segunda iteración en `reports/figures/` provienen de esta ejecución. Los seis runs de la primera iteración, reejecutados, reproducen sus métricas de validación y entrenamiento con diferencias menores a 1e-9. No se repitió con el árbol limpio porque la diferencia era solo documental. Septiembre no se usó.

El Model Registry quedó con la versión 1 de cada modelo y el alias `champion`:

- `mibici-p1-demanda` → `P1_hgb_poisson_estacion_h1`, con etiqueta `supera_baselines=si`.
- `mibici-p2-riesgo` → `P2_hgb_ajustado_proxy_h1`, con etiqueta `supera_baselines=no: P2_persistencia_proxy_h1`, coherente con la sección del baseline de persistencia.

MLflow es local y no se versiona. `resultados_mlflow.json` conserva la primera iteración sin cambios y, en el bloque `segunda_iteracion`, los 23 runs principales y los 24 runs hijo de las búsquedas de esta ejecución, el Model Registry y la comparación con la primera iteración. Se omitieron las etiquetas `mlflow.source.name` y `mlflow.user`, que contienen la ruta y el usuario locales.

**Ejecución definitiva mediante MLflow Project.**

Las tablas de análisis de este documento conservan los resultados iniciales en validación. La reejecución definitiva se completó desde el commit limpio `92e305f3de71dada5853035ba0081401aad197be`, mediante MLflow Project y con `git_dirty=false`. Sus 52 runs, parámetros, métricas, versiones y los tres modelos elegidos se conservan en [resultados_mlflow_entrega2.json](resultados_mlflow_entrega2.json) y se explican en [resultados_mlflow_entrega2.md](resultados_mlflow_entrega2.md). Las capturas están en `figures/entrega2/` y en el nuevo reporte PDF.

La ejecución definitiva también evalúa septiembre para los finalistas P1/P2 como comparación retrospectiva; no cambia los hiperparámetros ni la selección con esas métricas. Las búsquedas y el análisis de sensibilidad siguen usando solo validación. Las menciones previas a no evaluar septiembre en este documento describen los análisis iniciales, no esa reejecución posterior.

Los nombres de las corridas, no sus IDs locales, se reproducen al ejecutar los comandos del README.
