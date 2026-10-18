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

Los tres candidatos se comparan solo con su baseline dentro de cada pregunta. La semilla 42 y las seis configuraciones se fijaron antes de la prueba; no se realizó búsqueda de hiperparámetros. Por tanto, no se atribuye causalmente la mejora a un único hiperparámetro.

## Trazabilidad y evidencia

Los seis runs finalizaron y registran `git_dirty=false`, el mismo commit, las mismas versiones de datos y variables, parámetros del estimador, etiquetas y al menos una figura. Las capturas auténticas de la interfaz están en `reports/figures/mlflow_*.png`; las tablas provienen del registro local y el JSON conserva la precisión completa. Los nombres de las corridas, no sus IDs locales, se reproducen al ejecutar los comandos del README.
