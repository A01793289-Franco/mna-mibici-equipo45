# Segunda entrega | Experimentos y Model Registry

La ejecución se lanzó desde el MLproject definitivo, en un clon limpio, con entorno creado por MLflow mediante uv y descarga real de los datos. Los enlaces del PDF apuntan a main; el commit de código y los run IDs conservan el linaje de la ejecución.

Código ejecutado: `92e305f3de71dada5853035ba0081401aad197be`.
Datos: `5ca52ccee062fbfea75de9d014ebe44884994e8cd2aa92d6a3d621465f8bee43`.
Variables: `87c1e6136a5f0466e7e1a678191cb414bba6378e7ed9159432b8a07832535fdd`.

## Verificación

- 74 pruebas de unidad e integración aprobadas.
- Ingesta y variables reconstruidas sin tablas preexistentes.
- Los hashes de los CSV y Parquet coinciden con la entrega previa; las versiones cambiaron por la configuración centralizada.
- 52 runs del protocolo de entrenamiento, incluido el padre, con 48 modelos guardados.
- Los 48 modelos tienen firma, ejemplo de entrada, manifiestos, configuración, figuras y metadatos de entrada.
- Tres champion cargados y comprobados con sus predicciones y métricas de validación.
- Una ejecución adicional de P3 con k=4 y semilla 123 comprobó la parametrización sin mover champion.

## P1

| Modelo | learning_rate | max_iter | max_leaf_nodes | MAE val. | MAE septiembre |
|---|---|---|---|---|---|
| P1_estacional_h1 | - | - | - | 0.898799 | 1.026387 |
| P1_hgb_poisson_h1 | 0.1 | 100 | 31 | 0.761427 | 0.871903 |
| P1_hgb_poisson_estacion_h1 | 0.1 | 100 | 31 | 0.749792 | 0.862040 |
| P1_hgb_poisson_ajustado_h1 | 0.05 | 300 | 63 | 0.755199 | 0.863446 |

Elegido: HGB con estación, por menor MAE de validación. La mejora del MAE no garantiza menor RMSE en todas las alternativas.

## P2

| Modelo | F1 macro val. | F1 macro septiembre | AP macro val. |
|---|---|---|---|
| P2_logistica_proxy_h1 | 0.822339 | 0.811433 | 0.903375 |
| P2_persistencia_proxy_h1 | 0.882361 | 0.869517 | 0.813029 |
| P2_hgb_proxy_h1 | 0.870816 | 0.857368 | 0.955667 |
| P2_hgb_ajustado_proxy_h1 | 0.872322 | 0.858592 | 0.957206 |

Elegido: persistencia, por mayor F1 macro y bajo costo. La AP de esta regla usa salidas 0/1; no son probabilidades calibradas. El resultado se refiere al inventario virtual, no a disponibilidad real.

## P3

| Algoritmo | k | Silhouette train | Davies-Bouldin train | ARI val. |
|---|---|---|---|---|
| kmeans | 2 | 0.132493 | 2.446397 | 0.457773 |
| kmeans | 3 | 0.140695 | 1.978430 | 0.577564 |
| kmeans | 4 | 0.113102 | 2.085410 | 0.372644 |
| kmeans | 5 | 0.116454 | 2.107666 | 0.292348 |
| kmeans | 6 | 0.096313 | 2.140887 | 0.372769 |
| kmeans | 7 | 0.074362 | 2.122336 | 0.273402 |
| kmeans | 8 | 0.071661 | 2.087755 | 0.338437 |
| ward | 2 | 0.103976 | 2.570836 | 0.139027 |
| ward | 3 | 0.123216 | 2.138794 | 0.311556 |
| ward | 4 | 0.068849 | 2.420720 | 0.176022 |
| ward | 5 | 0.075508 | 2.374779 | 0.152970 |
| ward | 6 | 0.078757 | 2.172772 | 0.151809 |
| ward | 7 | 0.083797 | 2.083515 | 0.152562 |
| ward | 8 | 0.067058 | 2.169141 | 0.183094 |

Elegido: K-means con tres grupos. Se prioriza estabilidad entre periodos; silhouette bajo indica separación limitada. Las métricas val_assignment_* corresponden al agrupador congelado y se distinguen de val_ari.

## Registry

| Pregunta | Modelo | Versión | Alias | Run |
|---|---|---|---|---|
| P1 | mibici-p1-demanda | 1 | champion | `da28d047b8384d089de6f74fcd4e175d` |
| P2 | mibici-p2-riesgo | 1 | champion | `fb52c91b260843a992fe74ecfac7201c` |
| P3 | mibici-p3-grupos | 1 | champion | `1079f92ad21d4f2cbc7dfa29c0d01253` |

Se utiliza champion como referencia de la versión elegida. Se comprueba carga y predicción antes de promover. Es un Registry local; no se desplegó un servicio operativo.

## Límites de interpretación

La selección utiliza validación. Septiembre ya se usó en la primera entrega y esta evaluación es retrospectiva, no una nueva prueba independiente. Las búsquedas P1/P2 ajustan una muestra de entrenamiento; los finalistas utilizan todo entrenamiento. Los tiempos son mediciones de una máquina y una ejecución, sin intervalos de estabilidad estadística.

## Evidencia

[Reporte en PDF](TC5061_Reporte_MLFlow_Equipo45.pdf), [parámetros y métricas completos](resultados_mlflow_entrega2.json), [guía de ejecución](../references/mlflow_project.md) y capturas en `figures/entrega2/`.
