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

## Elección y registro del modelo

Después de entrenar P1 y P2 se registra en MLflow Model Registry un modelo por pregunta y se le asigna el alias `champion`. La regla usa únicamente métricas de validación, nunca `test_`:

- P1 (`mibici-p1-demanda`): el modelo con menor `val_mae`.
- P2 (`mibici-p2-riesgo`): el modelo con mayor `val_f1_macro`; una métrica no definida descalifica al run.

Solo compiten los runs que guardan un estimador, porque el registro debe contener algo que se pueda cargar y usar. Los baselines sin modelo (estacional en P1, persistencia en P2) no se registran, pero se comparan: si uno supera al ganador en la métrica de elección, la versión registrada queda con la etiqueta `supera_baselines=no: <run>` y el entrenamiento lo avisa. Cada ejecución crea una versión nueva y mueve el alias al ganador. `python -m mibici.predict` usa siempre la versión con alias `champion`.

## Segunda iteración: ajuste de hiperparámetros

Después de la evaluación única de septiembre se añadió una búsqueda de hiperparámetros del boosting en P1 y P2 (`--tune`). Es una segunda iteración y queda declarada aquí:

- La cifra de septiembre de la primera iteración (configuración por defecto) queda como valor histórico y no se reutiliza para elegir hiperparámetros.
- La búsqueda usa solo validación. Cada combinación se entrena con una muestra aleatoria reproducible de 300,000 filas de entrenamiento (semilla 42) y se mide en toda la validación; no hay validación cruzada aleatoria ni se usa septiembre. Los runs hijo nunca calculan métricas `test_`.
- La cuadrícula, con 12 combinaciones, es `learning_rate` {0.05, 0.1}, `max_leaf_nodes` {15, 31, 63} y `max_iter` {100, 300}. Vive en `mibici/train.py` y no en `config.py`, cuyo hash forma parte de los manifiestos de datos.
- La mejor combinación según la métrica de elección (`val_mae` en P1, `val_f1_macro` en P2) se reentrena con todo el entrenamiento y se registra como candidato adicional (`P1_hgb_poisson_ajustado_h1`, `P2_hgb_ajustado_proxy_h1`).
- Los modelos ajustados no se han evaluado en septiembre. Si se decide hacerlo, se hará una sola vez con `--final-test` y se anotará aquí, sin cambiar de nuevo hiperparámetros.

## Baseline de persistencia en P2

La etiqueta de P2 es la clase de la ocupación virtual de la hora siguiente, y la ocupación virtual de la hora actual es un predictor. La regla `P2_persistencia_proxy_h1` predice que la clase no cambia: "sin bicicletas" si `virtual_occupancy <= 0.10`, "sin anclajes" si `>= 0.90`, "normal" en otro caso. Usa los umbrales que definen la etiqueta y no tiene parámetros que ajustar con datos, por lo que no hay búsqueda de hiperparámetros. Se agregó después de la evaluación única de septiembre, como control de rigor; su comparación se hace en validación y no se calculó para septiembre, de modo que esa evaluación no se vuelve a usar.

## Comandos

```bash
python -m mibici.dataset --verify
python -m mibici.features --verify
python -m unittest discover -s tests -v
python -m mibici.train --question all --final-test
python -m mibici.train --question all --tune
python -m mibici.predict --question P1 --timestamp 2026-09-15T08:00
python -m mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5000
```

La ejecución requiere primero la ingesta y las variables del README. El notebook es exploratorio y se puede ejecutar con Jupyter. No contiene entrenamiento ni comentarios en las celdas de código.
