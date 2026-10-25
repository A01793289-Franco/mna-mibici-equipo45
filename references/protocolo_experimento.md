# Protocolo del experimento base | Equipo 45

Las seis configuraciones y la semilla 42 quedan fijadas en Git antes de ejecutar el experimento. No se buscan hiperparámetros ni se modifica un modelo después de observar septiembre.

- Entrenamiento: enero-junio, excluyendo la historia inicial insuficiente.
- Validación: julio-agosto; se comparan las configuraciones propuestas.
- Prueba final: septiembre; se evalúa una vez por configuración de P1/P2 mediante `--final-test`, después de fijar este protocolo.
- P3 compara perfiles de entrenamiento y validación mediante ARI entre estaciones comunes. La versión actual no calcula métricas de prueba para P3; no se atribuyen resultados de septiembre a esta pregunta.
- P1: estacional semanal y `HistGradientBoostingRegressor(loss="poisson")`.
- P2: regresión logística balanceada con escalado aprendido en entrenamiento y `HistGradientBoostingClassifier(class_weight="balanced")`. Se agregó después un tercer baseline sin aprendizaje, `P2_persistencia_proxy_h1` (véase abajo).
- P3: K-means y Ward, ambos con tres grupos. Las coordenadas se reservan para el mapa.

La prueba no se usa para cambiar estos modelos. El valor inicial de ocupación virtual utilizado en esta entrega es 0.5.

Cada run registra commit real, versiones de datos y variables, fechas, semilla, hiperparámetros del estimador, métricas por conjunto y artefactos. Las figuras son agregadas y no muestran personas usuarias.

Las funciones de `features.py` incluyen docstrings sobre su operación y su pertinencia para P1-P3. La documentación Markdown amplía los supuestos y las decisiones del proyecto.

## Barrido de k en P3

k=3 se fijó antes del experimento. Para contrastarlo se agregó el run `P3_barrido_k_perfil48`, que entrena K-means y Ward con k de 2 a 8 y registra silhouette, Davies-Bouldin y ARI por k. Usa únicamente `p3_train` y `p3_val`; `p3_test.parquet` no se lee ni se usa para decidir. El rango de k vive en `mibici/train.py` (`P3_K_VALUES`). La decisión sobre k y su interpretación están en `reports/resultados_mlflow.md`.

## Estación como variable categórica en P1

Se agregó `P1_hgb_poisson_estacion_h1`, que usa `station_id` como categórica. Es otra iteración posterior a septiembre, por lo que se evalúa en validación y no se evaluó en septiembre. Las categorías se aprenden solo con el entrenamiento: las 254 estaciones con más filas (empate por `station_id`) conservan su categoría y el resto, más las estaciones no vistas, se agrupan en "otras". Las columnas (`P1_FEATURE_COLUMNS_V2`) y la codificación están en `mibici/train.py` y `mibici/stations.py`, no en `config.py`, cuyo hash forma parte de los manifiestos de datos; `P1_FEATURE_COLUMNS` queda sin cambios.

## Elección y registro del modelo

La integración de la segunda entrega guarda modelos para las tres preguntas y conserva el alias `champion`. La regla principal usa solo validación: menor `val_mae` en P1, mayor `val_f1_macro` en P2 y mayor `val_ari` de estabilidad entre periodos en P3. Las reglas estacional y de persistencia son serializables y pueden ganar. Las métricas de prueba no participan en la elección.

Cada versión conserva descripción, run, experimento, commit y versiones de datos y variables. Antes de mover el alias se carga y comprueba la versión nueva; una comprobación fallida conserva el campeón anterior. Los detalles sobre artefactos, costos, desempates, asignación de P3 y compatibilidad con Projects están en [integracion_registry.md](integracion_registry.md).

## Segunda iteración: ajuste de hiperparámetros

Después de la evaluación única de septiembre se añadió una búsqueda de hiperparámetros del boosting en P1 y P2 (`--tune`). Es una segunda iteración y queda declarada aquí:

- La cifra de septiembre de la primera iteración (configuración por defecto) queda como valor histórico y no se reutiliza para elegir hiperparámetros.
- La búsqueda usa solo validación. Cada combinación se entrena con una muestra aleatoria reproducible de 300,000 filas de entrenamiento (semilla 42) y se mide en toda la validación; no hay validación cruzada aleatoria ni se usa septiembre. Los runs hijo nunca calculan métricas `test_`.
- La cuadrícula, con 12 combinaciones, es `learning_rate` {0.05, 0.1}, `max_leaf_nodes` {15, 31, 63} y `max_iter` {100, 300}. Vive en `mibici/train.py` y no en `config.py`, cuyo hash forma parte de los manifiestos de datos.
- La mejor combinación según la métrica de elección (`val_mae` en P1, `val_f1_macro` en P2) se reentrena con todo el entrenamiento y se registra como candidato adicional (`P1_hgb_poisson_ajustado_h1`, `P2_hgb_ajustado_proxy_h1`).
- Los modelos ajustados no se han evaluado en septiembre. Si se decide hacerlo, se hará una sola vez con `--final-test` y se anotará aquí, sin cambiar de nuevo hiperparámetros.

## Baseline de persistencia en P2

La etiqueta de P2 es la clase de la ocupación virtual de la hora siguiente, y la ocupación virtual de la hora actual es un predictor. La regla `P2_persistencia_proxy_h1` predice que la clase no cambia: "sin bicicletas" si `virtual_occupancy <= 0.10`, "sin anclajes" si `>= 0.90`, "normal" en otro caso. Usa los umbrales que definen la etiqueta y no tiene parámetros que ajustar con datos, por lo que no hay búsqueda de hiperparámetros. Se agregó después de la evaluación única de septiembre, como control de rigor; su comparación se hace en validación y no se calculó para septiembre, de modo que esa evaluación no se vuelve a usar.

## Sensibilidad de P2 a la ocupación inicial

La ocupación virtual parte de un valor arbitrario (`INITIAL_OCCUPANCY = 0.5`). `python -m mibici.sensitivity` repite P2 con 0.25, 0.5 y 0.75 (`P2_INITIAL_OCCUPANCY_CHECKS`) reconstruyendo la tabla en memoria con `features.p2_features`, sin escribir Parquet ni manifiestos. Los tres modelos se entrenan y evalúan igual que en el experimento base, solo con validación y sin registrar modelos en el Model Registry. Se compara el F1 macro, la exactitud balanceada, la proporción de clases y los eventos recortados. No se elige una ocupación inicial a partir de estos resultados.

## Comandos

```bash
python -m mibici.dataset --verify
python -m mibici.features --verify
python -m unittest discover -s tests -v
python -m mibici.train --question all --final-test
python -m mibici.train --question all --tune
python -m mibici.sensitivity
python -m mibici.predict --question P1 --timestamp 2026-09-15T08:00
python -m mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5000
```

La ejecución requiere primero la ingesta y las variables del README. El notebook es exploratorio y se puede ejecutar con Jupyter. No contiene entrenamiento ni comentarios en las celdas de código.
