# MLflow Project | Equipo 45

## Ejecución desde un clon limpio

Se utilizan el mismo repositorio, rango de datos, partición y experimento de la primera entrega. Los archivos `MLproject` y `python_env.yaml` están en la raíz. El entorno declara Python 3.13.15 y usa las versiones fijas de `requirements.txt`, que también instala el paquete local. No es necesario modificar el código para elegir un modelo.

Primero se clona el repositorio, se crea el entorno de la sección Instalación del README y se instalan las dependencias. En una terminal, situada en la raíz, se inicia el servidor:

```text
python -m mlflow server --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1 --port 5000
```

En otra terminal, con el mismo entorno activado, se define la conexión:

| Sistema | Comando |
|---|---|
| Linux/macOS | `export MLFLOW_TRACKING_URI=http://127.0.0.1:5000` |
| PowerShell | `$env:MLFLOW_TRACKING_URI="http://127.0.0.1:5000"` |
| CMD | `set MLFLOW_TRACKING_URI=http://127.0.0.1:5000` |

Con las dependencias ya instaladas y el entorno activado, los mismos comandos funcionan en los tres sistemas:

```text
python -m mlflow run . -e ingest --env-manager local --experiment-name mibici-equipo45
python -m mlflow run . -e train --env-manager local --experiment-name mibici-equipo45 -P question=all -P tune=true
python -m mlflow run . -e verify --env-manager local --experiment-name mibici-equipo45
```

`ingest` descarga los nueve CSV y el catálogo, normaliza y construye las variables. No requiere subir archivos ni ejecutar un notebook. Reutiliza descargas con SHA-256 verificado. Para aceptar deliberadamente cambios de la fuente se puede usar `-P refresh=true`.

`--env-manager local` utiliza el entorno activo que se instaló siguiendo el README; no instala otro. Para que MLflow cree el entorno declarado automáticamente se puede sustituir por `--env-manager uv`, con uv instalado. La especificación `python_env.yaml` se conserva en ambos casos. El entrenamiento se lanza siempre mediante `mlflow run`.

La interfaz queda en http://127.0.0.1:5000. Una dirección local no da acceso remoto al profesor; el reporte contiene las capturas y los comandos permiten reconstruir la evidencia.

## Modelos y parámetros

| Pregunta | Valores de `model` |
|---|---|
| p1 | `all`, `seasonal`, `hgb`, `hgb_station` |
| p2 | `all`, `persistence`, `logistic`, `hgb` |
| p3 | `all`, `kmeans`, `ward` |

P1 mantiene la regla estacional al ejecutar un HGB específico. P2 mantiene la persistencia al ejecutar logística o HGB. Así se conserva una comparación local con la regla sencilla. P3 permite ejecutar un agrupador concreto, o `all` para comparar ambos y el barrido de k.

| Parámetro | Uso | Valor central |
|---|---|---|
| `seed` | Muestreo, estimadores y agrupamientos independientes de validación | `config.SEED` |
| `learning_rate` | HGB de P1/P2 | `config.HGB_DEFAULTS` |
| `max_iter` | HGB o logística | `config.HGB_DEFAULTS` / `config.LOGISTIC_DEFAULTS` |
| `max_leaf_nodes` | HGB | `config.HGB_DEFAULTS` |
| `l2_regularization` | HGB | `config.HGB_DEFAULTS` |
| `c` | P2, `model=logistic` | `config.LOGISTIC_DEFAULTS['C']` |
| `n_clusters` | P3 | `config.N_CLUSTERS` |
| `tune` | Búsquedas de P1/P2, con `model=all` | `config.PROJECT_TUNE`, falso |
| `final_test` | Añade septiembre en P1/P2 | `config.PROJECT_FINAL_TEST`, falso |
| `register` | Crea versión y comprueba el alias | `config.PROJECT_REGISTER`, verdadero en `model=all`; falso para un modelo concreto |

El valor especial `config` en el YAML resuelve el valor desde Python, porque MLproject no importa expresiones de `config.py`. Evita duplicar fechas, rutas y semillas. Los valores numéricos explícitos se validan antes de leer datos. Los booleanos aceptan `true` o `false`. Parámetros incompatibles con la pregunta o el modelo producen un error.

En una búsqueda, las combinaciones de `SEARCH_GRID` determinan learning_rate, max_iter y max_leaf_nodes; una regularización explícita se conserva. La muestra de búsqueda es de hasta 300,000 filas de entrenamiento, mientras que los finalistas se ajustan con todo entrenamiento. No se presentan como si hubieran utilizado el mismo tamaño de ajuste.

Ejemplos con hiperparámetros explícitos:

```text
python -m mlflow run . -e train --env-manager local --experiment-name mibici-equipo45 -P question=p1 -P model=hgb_station -P learning_rate=0.1 -P max_iter=100 -P max_leaf_nodes=31 -P seed=42
python -m mlflow run . -e train --env-manager local --experiment-name mibici-equipo45 -P question=p2 -P model=logistic -P c=0.5 -P max_iter=1000 -P seed=42
python -m mlflow run . -e train --env-manager local --experiment-name mibici-equipo45 -P question=p3 -P model=kmeans -P n_clusters=3 -P seed=42
```

Para reproducir los modelos seleccionados por validación, se utiliza `hgb_station` en P1, `persistence` en P2 y `kmeans` con tres grupos en P3. Un modelo concreto no cambia `champion` salvo que se indique `-P register=true`. El protocolo completo compara sus candidatos y sí registra el ganador de cada pregunta.

## Configuración, versiones y trazabilidad

`mibici/project.py` resuelve los argumentos y coordina la entrada de ingesta. `mibici/train.py` conserva las funciones de entrenamiento y registra los parámetros efectivos, no solamente los marcadores `config` del padre. El run creado por MLflow Project es el padre de modelos y búsquedas. Las combinaciones de cada búsqueda son sus hijos.

La incorporación de valores de entrenamiento en `config.py` cambia el hash de ese archivo y, por diseño del versionado, cambia las versiones de ingesta y variables. La reconstrucción conserva los SHA-256 de todos los CSV y Parquet. No cambian registros, partición, etiquetas ni predictores: las corridas históricas conservan su versión original y las nuevas registran los manifiestos vigentes.

Los modelos usan los aliases `champion` del Registry y conservan experimento, run, commit y versiones. Una validación de carga precede a la promoción. El [documento de integración](integracion_registry.md) explica las métricas, los adaptadores y sus límites.

Las métricas `test_` son una evaluación retrospectiva del septiembre ya utilizado en la primera entrega; no constituyen un nuevo conjunto nunca observado. La selección automática utiliza únicamente validación. Para registrar esa evaluación explícita, con el protocolo fijado, se añade `-P final_test=true`. P3 conserva su comparación entre periodos de entrenamiento y validación.

## Referencia

MLflow. (s. f.). *MLflow Projects*. https://mlflow.org/docs/latest/ml/projects/
