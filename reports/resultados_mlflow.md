# Resultados reales | Equipo 45

Commit de ejecución: `43bf339792fef5d01326aa0ca0227fdd781675ff`.

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

P3 favorece K-means frente a Ward en las tres métricas. K-means produce grupos de 213, 33 y 151 estaciones, con 397 estaciones comunes al comparar periodos. El ARI de 0.5776 indica estabilidad parcial, no coincidencia perfecta; silhouette de 0.1407 advierte superposición. Tres grupos fue una decisión inicial fijada antes del experimento. No se evaluó P3 sobre septiembre.

Los tres candidatos se comparan solo con su baseline dentro de cada pregunta. La semilla 42 y las seis configuraciones se fijaron antes de la prueba; la primera iteración no realizó búsqueda de hiperparámetros (la segunda se describe más abajo). Por tanto, no se atribuye causalmente la mejora a un único hiperparámetro.

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

## Trazabilidad y evidencia

Los seis runs finalizaron y registran `git_dirty=false`, el mismo commit, las mismas versiones de datos y variables, parámetros del estimador, etiquetas y al menos una figura. Las capturas auténticas de la interfaz están en `reports/figures/mlflow_*.png`; las tablas provienen del registro local y el JSON conserva la precisión completa. Los nombres de las corridas, no sus IDs locales, se reproducen al ejecutar los comandos del README.
