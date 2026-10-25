# Integración de Tracking y Model Registry | Equipo 45

## Alcance

Esta integración parte de `feature/mlops-improvements`, commit `f0acc9b`. Conserva la ingesta, las variables, las particiones y los experimentos de Efren. Añade el registro completo de artefactos, modelos recuperables para P1-P3 y verificaciones antes de mover un alias. Las explicaciones del código nuevo están en este documento; se conservan los comentarios previos de los compañeros.

## Módulos

| Archivo | Responsabilidad |
|---|---|
| `mibici/train.py` | Entrenamiento, métricas, búsquedas y selección por pregunta. |
| `mibici/deployable.py` | Estimadores que permiten guardar la regla estacional, la persistencia y los agrupadores. |
| `mibici/tracking.py` | Artefactos comunes, registro de entradas, compatibilidad con una corrida de MLflow Project y comprobación de carga. |
| `mibici/predict.py` | Predicción por hora para P1/P2 y asignación de perfiles a grupos para P3. |
| `mibici/verify_registry.py` | Carga por alias, reproducción de predicciones y métricas de validación. |

## Artefactos por corrida

Los baselines, las candidatas finales y las combinaciones hijas de las búsquedas guardan:

- Parámetros efectivos, semilla, fechas, cantidades, commit y versiones de datos y variables.
- Etiquetas `equipo`, `pregunta`, `question`, `tipo`, `stage_of_work` y `model_family`.
- `data/`: manifiestos de ingesta y variables, sin publicar los archivos de viajes.
- `config/`: configuración, código de entrenamiento, dependencias y parámetros efectivos en `execution.json`. Si existen `MLproject` y `python_env.yaml`, también se guardan.
- Modelo con firma, cinco ejemplos de entrada y el código del paquete. Se conserva la serialización con `skops` utilizada por el equipo.
- `config/model_check.json`: ejemplos y salidas de referencia para comprobar que la recuperación mantiene las predicciones.
- `figuras/`: comparación de demanda para P1, matriz de confusión y precisión-recall para P2, mapa y perfiles para P3.
- `tablas/`: asignaciones de estaciones y resúmenes de búsquedas cuando corresponda.
- Entrada de entrenamiento mediante `mlflow.log_input`: esquema, perfil y digest de variables agregadas por estación, sin identificadores de personas usuarias.

En MLflow 3, los modelos se consultan en Logged Models; no es necesario que aparezcan como una carpeta dentro de Artifacts del run.

Cada combinación del barrido de P3 tiene una corrida hija con modelo y artefactos propios. El padre conserva la tabla, figura e historial por k. Los hijos de las búsquedas de P1/P2 también guardan sus modelos y artefactos; entrenan con la muestra declarada, por lo que se distinguen de los finalistas ajustados con todo entrenamiento.

## Modelos y aliases

| Pregunta | Nombre conservado | Regla principal |
|---|---|---|
| P1 | `mibici-p1-demanda` | Menor `val_mae`. |
| P2 | `mibici-p2-riesgo` | Mayor `val_f1_macro`. |
| P3 | `mibici-p3-grupos` | Mayor `val_ari` de estabilidad entre periodos. |

Se conservan los nombres iniciales de P1/P2 para que los comandos del equipo sigan funcionando; las tres familias tienen la etiqueta de equipo 45. En empates exactos se consideran silhouette, Davies-Bouldin y, finalmente, el tiempo de inferencia medido sobre hasta 1,000 filas. También se registra `fit_seconds`. Los tiempos dependen del equipo y no demuestran por sí mismos estabilidad estadística.

Las reglas estacional y de persistencia ahora pueden guardarse y competir. Si la persistencia obtiene mejor F1 macro que el boosting, puede quedar como `champion`: ya no se excluye por carecer de un estimador serializable. Sus salidas 0/1 representan una regla determinista, no probabilidades calibradas.

Antes de mover `champion`, la nueva versión recibe un alias temporal, se carga desde el Registry y se comparan sus predicciones con las guardadas. Si falla, no se reemplaza el alias de producción. La versión conserva descripción, corrida y experimento de origen, commit y versiones de datos y variables. `--no-register` evita cambios en los aliases, aunque conserva los modelos de las corridas.

No se exige que un candidato supere al baseline para registrar un modelo útil: si el baseline gana, se puede registrar ese baseline. La decisión final debe explicar los errores de negocio, la estabilidad y el costo, además de la cifra principal.

## P3: estabilidad y uso posterior

`val_ari` conserva su definición original: concordancia entre dos agrupaciones ajustadas por separado en entrenamiento y validación, restringida a estaciones comunes. No se presenta como exactitud de predicción ni como una evaluación supervisada.

El agrupador de producción se ajusta únicamente en entrenamiento:

- K-means asigna un perfil nuevo al centroide de entrenamiento más cercano.
- Ward no tiene `predict` nativo. Su adaptador asigna el grupo del perfil de entrenamiento más cercano mediante 1-NN. Es una regla adicional explícita; no vuelve a ajustar Ward sobre los perfiles nuevos.

`val_assignment_silhouette` y `val_assignment_davies_bouldin` evalúan la asignación del modelo congelado en validación. `val_assignment_ari` compara esas asignaciones con el agrupamiento independiente de validación. Estas métricas adicionales se distinguen de las métricas históricas.

## Interfaz para el MLflow Project de Franco

El entrenamiento respeta `MLFLOW_TRACKING_URI`; si no se define, conserva el backend SQLite de `config.py`. Con servidor HTTP, los experimentos nuevos usan el almacén de artefactos administrado por el servidor, en lugar de imponer una ruta local del cliente.

Cuando MLflow Projects establece `MLFLOW_RUN_ID`, `train.main` reabre esa corrida como padre. Cada modelo y búsqueda se registra como hijo; las combinaciones de una búsqueda quedan un nivel más abajo. Así no se cierra ni se reutiliza accidentalmente el padre para varios modelos.

El punto de entrada del Project puede invocar `python -m mibici.train --question P1 --tune` y sus equivalentes de P2/P3. Esta integración no crea el archivo raíz `MLproject` ni sustituye la tarea de parametrizarlo por modelo e hiperparámetros. El responsable de ese archivo debe conectar sus argumentos con las fábricas de modelos y conservar los valores centrales de fechas y semilla.

Ejemplo de servidor para el trabajo local:

```text
python -m mlflow server --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1 --port 5000
```

En otra terminal, desde la raíz del repositorio, se selecciona la URI:

| Sistema | Comando |
|---|---|
| Linux/macOS | `export MLFLOW_TRACKING_URI=http://127.0.0.1:5000` |
| PowerShell | `$env:MLFLOW_TRACKING_URI="http://127.0.0.1:5000"` |
| CMD | `set MLFLOW_TRACKING_URI=http://127.0.0.1:5000` |

Un experimento ya existente conserva su ubicación de artefactos. Si se mueve entre máquinas, hay que preservar los artefactos originales o migrar su almacén; cambiar solo la URI del cliente no mueve los archivos históricos.

## Comprobaciones y predicción

```text
python -m unittest discover -s tests -v
python -m mibici.dataset --verify
python -m mibici.features --verify
python -m mibici.verify_registry --question all --smoke-only
python -m mibici.verify_registry --question all
python -m mibici.predict --question P3 --split val --output reports/predicciones/p3_val.csv
```

La comprobación rápida usa los cinco ejemplos guardados. La completa vuelve a calcular las métricas del modelo recuperado sobre validación; no entrena ni lee septiembre. Comprueba además que las versiones locales coincidan con las del modelo.

`--figures-dir` permite separar las figuras de una ejecución de las evidencias históricas. Los datos, la base de MLflow y los modelos siguen fuera de Git. Las corridas definitivas de esta entrega se deben ejecutar mediante el MLflow Project cuando esté integrado, conservando las corridas anteriores como evidencia histórica.

## Referencias técnicas

- MLflow. (s. f.). [MLflow 3 migration guide](https://mlflow.org/docs/latest/genai/mlflow-3).
- MLflow. (s. f.). [Model Registry workflows](https://mlflow.org/docs/latest/ml/model-registry/workflow/).
- Scikit-learn. (s. f.). [AgglomerativeClustering](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.AgglomerativeClustering.html).
