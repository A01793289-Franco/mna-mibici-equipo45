# MiBici | Equipo 45

[![CI](https://github.com/A01793289-Franco/mna-mibici-equipo45/actions/workflows/ci.yml/badge.svg)](https://github.com/A01793289-Franco/mna-mibici-equipo45/actions/workflows/ci.yml)

Propuesta de Machine Learning para apoyar la operación de MiBici en Guadalajara.

| Pregunta | Definición acordada |
|---|---|
| P1: demanda | Viajes iniciados por estación durante la siguiente hora. |
| P2: riesgo | Riesgo virtual de falta de bicicletas o anclajes al cierre de la siguiente hora. |
| P3: patrones | Tres grupos iniciales por perfil horario de uso, ubicados en un mapa. |

## Segunda entrega: MLflow Project y Registry

[Reporte de experimentos en PDF](reports/TC5061_Reporte_MLFlow_Equipo45.pdf) · [Resultados e interpretación](reports/resultados_mlflow_entrega2.md) · [Registro completo](reports/resultados_mlflow_entrega2.json).

El Project definitivo está en `MLproject`, con entorno en `python_env.yaml`. Las entradas `ingest` y `train` permiten reconstruir los datos y elegir pregunta, modelo, hiperparámetros y semilla desde la terminal. El protocolo completo conserva las búsquedas anidadas y registra un modelo `champion` por pregunta.

La [guía del MLflow Project](references/mlflow_project.md) incluye servidor SQLite, conexión en Linux/macOS/PowerShell/CMD, comandos desde un clon limpio, opciones y explicación de versiones. Después de instalar el entorno y definir `MLFLOW_TRACKING_URI`, se ejecuta:

```text
python -m mlflow run . -e ingest --env-manager local --experiment-name mibici-equipo45
python -m mlflow run . -e train --env-manager local --experiment-name mibici-equipo45 -P question=all -P tune=true
python -m mlflow run . -e verify --env-manager local --experiment-name mibici-equipo45
```

Para que MLflow cree el entorno declarado, se puede usar `--env-manager uv` con uv instalado. `local` reutiliza el entorno activo con las versiones de `requirements.txt`.

## Primera entrega: propuesta y evidencia

Existen la estructura Cookiecutter, configuración, propuesta, ingesta reproducible, funciones de variables para P1-P3, entrenamiento con registro en MLflow (`mibici/train.py`), modelos guardados con firma, Model Registry con alias `champion` e inferencia (`mibici/predict.py`). La ingesta y las variables se ejecutaron con los nueve meses seleccionados.

El experimento tiene dos iteraciones. La **primera** son seis corridas (baseline y candidato por pregunta) ejecutadas desde el commit `43bf339792fef5d01326aa0ca0227fdd781675ff`, con `git_dirty=false`; P1-P2 incluyen la evaluación original de septiembre. La **segunda** agrega el baseline de persistencia de P2, el ajuste de hiperparámetros, la estación como variable categórica en P1, el barrido de k en P3, el análisis de errores de P1 y la sensibilidad de P2 a la ocupación inicial. Esas mejoras se estudiaron inicialmente solo en validación. La ejecución definitiva del MLflow Project también evalúa los finalistas P1/P2 en septiembre como comparación retrospectiva, sin usarlo para seleccionar modelos. La propuesta y las capturas `mlflow_*.png` corresponden a la primera iteración; el nuevo reporte y `reports/figures/entrega2/` documentan la ejecución definitiva.

- [PDF de la propuesta y evidencia](reports/TC5061_Propuesta_Proyecto_Equipo45.pdf).
- [Resultados e interpretación de ambas iteraciones](reports/resultados_mlflow.md) y [registro completo de métricas y parámetros de la primera iteración](reports/resultados_mlflow.json).
- [ML Canvas editable](references/ml_canvas.md).
- [ML Canvas en PDF](references/Machine%20Learning%20Canvas.pdf).
- [Propuesta: datos, partición, pipelines, modelos y métricas](references/propuesta.md).
- [Arquitectura y justificación](references/arquitectura.md).
- [Diagrama editable](references/arquitectura.svg).
- [Ingesta y variables: decisiones, comandos y limitaciones](references/ingesta_features.md).
- [Manifiesto de datos](references/data_manifest.json) y [manifiesto de variables](references/feature_manifest.json).

## Datos y configuración

Fuente: [datos abiertos de MiBici](https://www.mibici.net/es/datos-abiertos/). Se utilizaron nueve meses completos, enero-septiembre de 2026, y el catálogo de septiembre.

Entrenamiento: enero-junio; validación: julio-agosto; prueba: septiembre. Los intervalos incluyen inicio y excluyen fin. Las variables de cada hora solo usan eventos anteriores al momento de predecir.

La ingesta obtuvo **3,362,065 registros originales y 3,358,273 viajes válidos** en nueve meses: 3,034 registros inválidos y 758 duplicados descartados. Se observaron 471 IDs de estación; el catálogo contiene 480 estaciones válidas. Los IDs 405 y 407 no aparecen en él. Son cifras del rango descargado, no contadores globales del portal.

Las salidas contienen 2,556,542 filas de P1 y 2,551,458 de P2; los perfiles P3 incluyen 397 estaciones de entrenamiento, 468 de validación y 468 de prueba. Ver versiones, conteos y hashes en los manifiestos. La propuesta documenta las limitaciones del catálogo posterior y del riesgo simulado.

`mibici/config.py` centraliza rutas, fuentes, fechas, semilla, horizontes, umbrales y parámetros de clustering. `dataset.py`, `features.py` y `train.py` importan esos valores en lugar de repetirlos.

## Estructura actual

```text
mibici/
  __init__.py
  config.py
  dataset.py
  features.py
  train.py
  train_p1.py
  predict.py
  deployable.py
  tracking.py
  verify_registry.py
  project.py
  api.py
  stations.py
references/
  Machine Learning Canvas.pdf
  ml_canvas.md
  propuesta.md
  arquitectura.md
  arquitectura.svg
  ingesta_features.md
  condiciones_datos.md
  protocolo_experimento.md
  data_manifest.json
  feature_manifest.json
notebooks/1.0-lpa-exploracion-mibici.ipynb
notebooks/2.0-analisis-errores-p1.ipynb
models/
reports/
  TC5061_Propuesta_Proyecto_Equipo45.pdf
  resultados_mlflow.json
  resultados_mlflow.md
  ingesta_features_verificacion.json
  ingesta_features_pruebas.txt
  documentacion_features_verificacion.json
  figures/
tests/
  test_data_features.py
  test_train.py
  test_predict.py
  test_stations.py
  test_sensitivity.py
docs/
requirements.txt
pyproject.toml
MLproject
python_env.yaml
```

`python -m mibici.config` crea `data/raw`, `data/interim` y `data/processed` localmente, sin versionar datos. `notebooks` se reserva para exploración; `models` para salidas locales y `reports/figures` para evidencia sin datos personales.

## Instalación

Se conserva Python 3.13 de la plantilla. Desde la raíz, en Linux o macOS:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m mibici.config
```

En Windows con PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m mibici.config
```

En Windows con CMD, activar el mismo entorno con `.venv\Scripts\activate.bat`. Las dependencias directas tienen versiones fijas. No se necesita WSL ni `make`. Las mejoras iniciales se reprodujeron también en Windows (pruebas, regeneración de ingesta y variables, ambos `--verify`, predicción, ajuste y sensibilidad). El MLflow Project definitivo completo se comprobó en Linux. CI ejecuta pruebas y documentación en Ubuntu y Windows; macOS usa los comandos equivalentes indicados.

## Ingesta y variables

Con el entorno activado, en cualquiera de los tres sistemas:

```bash
python -m mibici.dataset
python -m mibici.features
python -m mibici.dataset --verify
python -m mibici.features --verify
python -m pytest -v
```

La primera ejecución descarga los CSV; las posteriores reutilizan los archivos y verifican sus hashes. `--refresh` permite aceptar una actualización de la fuente. `--help` muestra fechas, carpeta alternativa y escenarios del proxy. La ingesta usa bloques; las agregaciones de variables reúnen los eventos del rango en memoria. Se requiere espacio local y memoria suficientes para millones de viajes.

La información personal no se incluye en Parquet de modelado. Las tablas agregadas se guardan en `data/processed`; las limpias mensuales, en `data/interim`. [La documentación](references/ingesta_features.md) explica las columnas permitidas como predictores, supuestos de cobertura y manejo del proxy.

## Experimento base en MLflow

Con los datos y las variables ya generados (sección anterior), desde la raíz y con el entorno activado:

```bash
python -m mibici.train --question all
python -m mlflow ui --backend-store-uri sqlite:///mlflow.db
```

Para repetir además la búsqueda de hiperparámetros del boosting (P1 y P2; unos 2 y 5 minutos respectivamente con 300,000 filas de muestra), agrega `--tune`:

```bash
python -m mibici.train --question all --tune
```

Crea un run padre `P1_busqueda_hgb_h1` (y `P2_busqueda_hgb_h1`) con un run hijo por combinación y, a partir de la mejor, los runs `P1_hgb_poisson_ajustado_h1` y `P2_hgb_ajustado_proxy_h1`. La cuadrícula está documentada en el [protocolo](references/protocolo_experimento.md). Para compararlas en la interfaz (modo *Model training*), expande el run padre en la tabla de runs, marca sus hijos y pulsa *Compare*.

La interfaz queda en <http://127.0.0.1:5000>, experimento `mibici-equipo45`. `python -m mibici.train_p1` sigue funcionando y equivale a `--question P1`.

| Run | Pregunta | Modelo | Métricas principales (validación) |
|---|---|---|---|
| `P1_estacional_h1` | P1 | Baseline: misma estación y hora de la semana anterior | `val_mae`, `val_rmse`, `val_wape` |
| `P1_hgb_poisson_h1` | P1 | `HistGradientBoostingRegressor` con pérdida de Poisson | `val_mae`, `val_rmse`, `val_wape` |
| `P1_hgb_poisson_estacion_h1` | P1 | Boosting de Poisson con la estación como variable categórica (254 estaciones frecuentes y "otras") | `val_mae`, `val_rmse`, `val_wape` |
| `P2_persistencia_proxy_h1` | P2 | Baseline sin aprendizaje: la clase de la próxima hora es la de la ocupación virtual actual | `val_f1_macro`, `val_balanced_accuracy`, `val_ap_macro` |
| `P2_logistica_proxy_h1` | P2 | Baseline: regresión logística balanceada de tres clases | `val_f1_macro`, `val_balanced_accuracy`, `val_ap_macro` |
| `P2_hgb_proxy_h1` | P2 | `HistGradientBoostingClassifier` balanceado | `val_f1_macro`, `val_balanced_accuracy`, `val_ap_macro` |
| `P1_hgb_poisson_ajustado_h1`, `P2_hgb_ajustado_proxy_h1` | P1, P2 | Con `--tune`: boosting con la mejor combinación de la búsqueda (solo validación) | `val_mae` / `val_f1_macro` |
| `P3_kmeans_perfil48` | P3 | Baseline: K-means con k=3 | `train_silhouette`, `train_davies_bouldin`, `val_ari` |
| `P3_ward_perfil48` | P3 | Agrupamiento jerárquico Ward con k=3 | `train_silhouette`, `train_davies_bouldin`, `val_ari` |
| `P3_barrido_k_perfil48` | P3 | Barrido de k=2 a 8 para K-means y Ward (una métrica por paso k, tabla y figura) | `*_train_silhouette`, `*_train_davies_bouldin`, `*_val_ari` |
| `P2_*_h1_occ25`, `_occ50`, `_occ75`, `P2_sensibilidad_ocupacion_inicial` | P2 | Con `python -m mibici.sensitivity`: los tres modelos de P2 con la ocupación inicial del proxy en 25%, 50% y 75%, y un run resumen | `val_f1_macro`, `val_balanced_accuracy` |

Cada run registra:

- **Etiquetas:** `equipo`, `pregunta` (P1, P2 o P3), `tipo` (baseline o candidato), `git_commit` y `git_dirty`.
- **Parámetros:** semilla, fechas de partición, horizonte, `data_version`, `feature_version`, columnas usadas, filas por conjunto y los parámetros del modelo.
- **Métricas:** con prefijo `val_` (y `train_` en P3). Una métrica no definida, por ejemplo la AP de una clase sin ejemplos, no se registra y queda anotada en la etiqueta `metricas_no_definidas`.
- **Artefactos:** figura de cada run (demanda por hora, matriz de confusión, o mapa y perfiles de los grupos) y, en P3, la tabla de grupos por estación. Las figuras también se guardan en `reports/figures/`.

Para que el commit registrado describa el código exacto, hay que correr el entrenamiento después de confirmar los cambios (`git_dirty` debe ser `false`). La prueba (septiembre) no se usa por defecto: `--final-test` añade las métricas `test_` y debe ejecutarse una sola vez, cuando las decisiones ya estén fijas. `mlflow.db` y `mlartifacts/` están en `.gitignore`: cada integrante reproduce los runs en su máquina.

### Sensibilidad de P2 a la ocupación inicial

La etiqueta de P2 parte de una ocupación virtual inicial arbitraria (50%). Para ver si las conclusiones dependen de ese supuesto:

```bash
python -m mibici.sensitivity
```

Recalcula la tabla de P2 **en memoria** con 25%, 50% y 75%, entrena persistencia, regresión logística y boosting con cada una, y registra un run por modelo y escenario (sufijo `_occ25`, `_occ50`, `_occ75`, parámetro `initial_occupancy`) más un run resumen. Tarda unos 3 minutos. No escribe tablas ni manifiestos (por eso no usa `features --initial-occupancy`, que sobrescribiría `data/processed/` y `feature_manifest.json`), no promueve modelos en el Registry y solo usa validación. Comprueba además que la tabla en memoria con 50% es idéntica a la guardada. Resultados en [reports/resultados_mlflow.md](reports/resultados_mlflow.md) y figura en `reports/figures/sensibilidad/`.

### Modelo guardado, registro y predicción

La integración de Tracking y Registry se documenta en [integracion_registry.md](references/integracion_registry.md). Los modelos de P1, P2 y P3, incluidas las reglas simples y cada combinación hija de búsqueda, se guardan con firma y ejemplo de entrada. Cada corrida añade los manifiestos en `data/`, la configuración efectiva en `config/` y una entrada de entrenamiento mediante `mlflow.log_input`. Las figuras y tablas permanecen organizadas en `figuras/` y `tablas/`.

Se conserva `val_mae` como criterio de P1 y `val_f1_macro` en P2; P3 usa el ARI entre periodos y considera las métricas geométricas para desempatar. Las reglas simples también pueden ganar. Los modelos registrados se llaman `mibici-p1-demanda`, `mibici-p2-riesgo` y `mibici-p3-grupos`. Cada versión tiene descripción, linaje y alias `champion`, que solo se mueve después de comprobar una carga y predicción desde el Registry. `--no-register` conserva las corridas sin modificar los aliases.

K-means asigna perfiles nuevos por centroide; Ward utiliza una regla explícita de vecino de entrenamiento más cercano. No se vuelve a ajustar el agrupador para predecir. Las métricas `val_assignment_*` distinguen ese uso de la estabilidad histórica `val_ari`.

El cliente respeta `MLFLOW_TRACKING_URI` y el run padre de MLflow Projects. Los detalles y las ejecuciones parametrizadas están en la guía del MLflow Project. Las corridas de la segunda entrega se lanzan mediante sus entradas.

```bash
python -m mibici.predict --question P1 --timestamp 2026-09-15T08:00
python -m mibici.predict --question P2 --timestamp 2026-09-15T08:00 --output salida.csv
python -m mibici.predict --question P3 --split val
python -m mibici.verify_registry --question all
```

`predict.py` carga el modelo `champion`, toma de la tabla de variables que construye `features.py` las filas de esa hora (en hora local de Ciudad de México si no se indica zona) y escribe `reports/predicciones/p1_20260915T0800.csv`, con una fila por estación: `demanda_esperada` en P1, y `clase`, `riesgo` y las tres probabilidades en P2. Si la hora no está en la tabla, por ejemplo por falta de 168 h de historia, termina con un mensaje que indica el rango disponible. Solo predice horas cuyas variables ya existen en la tabla; no calcula rezagos de horas futuras. En P2 el riesgo es el del estado virtual, no inventario observado.

El protocolo fijado antes de la evaluación final está en [protocolo_experimento.md](references/protocolo_experimento.md).

Notebook exploratorio: [1.0-lpa-exploracion-mibici.ipynb](notebooks/1.0-lpa-exploracion-mibici.ipynb). Las explicaciones están en Markdown y las celdas de código no contienen comentarios.

Análisis de errores de P1: [2.0-analisis-errores-p1.ipynb](notebooks/2.0-analisis-errores-p1.ipynb). Descompone el error del modelo `champion` por hora, por decil de demanda y por estación (solo validación) y concluye dónde falla; las conclusiones están resumidas en [resultados_mlflow.md](reports/resultados_mlflow.md). Requiere haber entrenado antes (carga el modelo del registro de MLflow). Para ejecutarlo de principio a fin desde la raíz:

```bash
python -c "import nbformat; from nbclient import NotebookClient; nb = nbformat.read('notebooks/2.0-analisis-errores-p1.ipynb', 4); NotebookClient(nb, resources={'metadata': {'path': 'notebooks'}}).execute(); nbformat.write(nb, 'notebooks/2.0-analisis-errores-p1.ipynb')"
```

También se puede abrir en VS Code o Jupyter y usar *Run All*.

Las funciones de `mibici/features.py` incluyen docstrings que describen qué hacen, para qué pregunta son pertinentes y cómo respetan la disponibilidad temporal de la información. `config.py`, `dataset.py` y `train.py` también documentan sus módulos y funciones principales. La [guía de ingesta y variables](references/ingesta_features.md) contiene las explicaciones ampliadas.

Las seis corridas de la primera iteración conservan el commit de ejecución y las versiones que registraron originalmente: `data_version` `4bd1e3ec…` y `feature_version` `b588c619…`. Después, dos cambios solo de documentación actualizaron los hashes de código y, con ellos, las versiones de los manifiestos. Los docstrings de `features.py` cambiaron `feature_version`; los de `config.py` y `dataset.py` cambiaron también `data_version`. En ambos casos la reconstrucción conservó los hashes de los CSV y de los Parquet. Esta [verificación](reports/documentacion_features_verificacion.json) documenta el primer cambio; el segundo se comprueba en el historial de Git de los manifiestos, donde solo cambian hashes de código, versiones y `created_at`.

## API local y documentación

Con los datos y los modelos `champion` ya generados, y la misma `MLFLOW_TRACKING_URI` del entrenamiento:

```text
python -m uvicorn mibici.api:app --host 127.0.0.1 --port 8000
```

La documentación interactiva está en <http://127.0.0.1:8000/docs>. `POST /predict` recibe `question` (P1/P2), `station_id` y `timestamp`; devuelve la predicción de la estación. Reutiliza las variables existentes y el alias vigente. No calcula horas futuras ni consulta inventario real. La [guía de la API](docs/docs/api.md) contiene ejemplos y códigos de error. P3 se conserva en el módulo de consola.

El sitio de documentación se construye desde la raíz:

```text
python -m mkdocs build --strict -f docs/mkdocs.yml
python -m mkdocs serve -f docs/mkdocs.yml -a 127.0.0.1:8001
```

[Inicio de documentación](docs/docs/index.md), [instalación y ejecución](docs/docs/getting-started.md) y [pruebas y CI](docs/docs/verificacion.md) describen el flujo real del proyecto.

GitHub Actions ejecuta lint, pruebas con datos sintéticos y MkDocs estricto en Ubuntu y Windows, más un trabajo de seguridad. La suite actual tiene 172 pruebas, incluidas nueve de la API, y pasa localmente junto con lint y MkDocs estricto. La API también se comprobó contra los champion reales de P1 y P2. El estado de las ejecuciones remotas se consulta en la insignia de CI y en el PR. El reporte conserva la evidencia de sus corridas originales; estos cambios añaden una interfaz local y comprobaciones de calidad.

## Calidad, validación de datos y seguridad

```text
python -m pip install -r requirements-validation.txt
python -m pytest -v
python -m mibici.validation
```

- **Pruebas (PyTest):** `tests/` reúne las pruebas `unittest` existentes y las nuevas de PyTest con fixtures en `tests/conftest.py`: utilidades de ingesta (`column_mapping`, `csv_format`, `canonical_hash`, `data_path`), la cuadrícula horaria `hourly_counts`, reproducibilidad del entrenamiento y controles de seguridad.
- **Reproducibilidad:** `tests/test_reproducibility.py` entrena dos veces con la misma semilla y exige predicciones, métricas registradas en MLflow, modelos guardados y CSV de grupos idénticos. Una prueba de control confirma que otra semilla cambia el boosting.
- **Validación de datos (DeepChecks):** `mibici/validation.py` revisa tipos, nulos, duplicados, rangos y coherencia del calendario y la partición (bloqueantes), y el drift entre entrenamiento, validación y prueba (informativo). La evidencia se guarda en [reports/deepchecks/resumen.md](reports/deepchecks/resumen.md) y su JSON; `--html` escribe además reportes interactivos, fuera de Git por tamaño. Requiere `requirements-validation.txt` porque deepchecks 0.19.1 necesita adaptaciones para numpy 2, pandas 3 y scikit-learn 1.9.
- **Seguridad:** `.env.example` documenta la única variable de entorno; `.env`, `mlflow.db` y los datos están excluidos. CI audita dependencias con `pip-audit` y el código con `bandit`. La API rechaza con 422 entradas inválidas o fuera de rango antes de cargar modelos.

[Pruebas y CI](docs/docs/verificacion.md) detalla cada control y las vulnerabilidades revisadas.

## Flujo de trabajo

- Ramas `feat/descripcion`, `fix/descripcion`, `docs/descripcion` o `chore/descripcion`.
- Commits `tipo: descripción`, por ejemplo `feat: agrega ingesta mensual`.
- Cada cambio entra mediante Pull Request revisado por otro integrante.

## Integrantes y responsabilidades

| Integrante | Responsabilidad |
|---|---|
| Franco Francisco Peña Colorado | Administrador del repositorio, estructura inicial y entrenamiento inicial P1. |
| Efren Pazzi Manzano | Canvas y entrenamiento P1-P3 con registro en MLflow. |
| Leonardo Peraza Alavez | Propuesta, ingesta, variables, versionado, notebook exploratorio y preparación del reporte. |
| Aldo Isai Pérez Hernández | Revisión e interpretación. |

## Reproducibilidad y privacidad

Los manifiestos versionan URL, SHA-256, código y conteos sin publicar archivos de datos. La versión de variables referencia la versión de ingesta. Cada run registra esas versiones, commit, pregunta, fechas, semilla, modelo, parámetros, métricas con prefijo y al menos un artefacto.

`.gitignore` excluye datos, modelos serializados, `mlruns`, `mlartifacts`, la base local de MLflow y archivos de entorno. MIT cubre el código; las condiciones publicadas de los datos y sus límites se documentan en [condiciones_datos.md](references/condiciones_datos.md).

## Evidencia y resultados obtenidos

**Primera iteración (evaluación original de septiembre)**

| Pregunta | Baseline | Candidato | Interpretación |
|---|---|---|---|
| P1 | MAE de prueba: 1.0264 | MAE de prueba: 0.8719 | El candidato reduce el error absoluto alrededor de 15.1%; aún tiene WAPE de 60.39%. |
| P2 | F1 macro de prueba: 0.8114 | F1 macro de prueba: 0.8574 | Mejora la concordancia con el proxy; no demuestra disponibilidad real. |
| P3 | K-means: silhouette 0.1407, ARI 0.5776 | Ward: silhouette 0.1232, ARI 0.3116 | K-means resulta preferible, pero los perfiles se superponen. |

**Mejoras iniciales de la segunda iteración (solo validación)**

| Pregunta | Resultado | Interpretación |
|---|---|---|
| P1 | La estación categórica obtiene `val_mae` 0.7498 frente a 0.7614 del boosting por defecto y 0.8988 del estacional. | Mejora de cerca de 1.5% frente al boosting por defecto. El análisis de errores distingue estaciones-hora de poca y alta demanda. |
| P2 | Persistencia obtiene F1 macro 0.8824 frente a 0.8708 del boosting y 0.8223 de la logística. | El resultado mide concordancia con el proxy. La sensibilidad de ocupación inicial entre 25% y 75% cambia el F1 menos de 0.0011. |
| P3 | El barrido de k=2 a 8 favorece k=3, con silhouette 0.1407 y ARI 0.5776. | Los perfiles permiten interpretar usos matutinos, vespertinos y de fin de semana, con superposición entre grupos. |

**Ejecución definitiva de la segunda entrega**

El commit `92e305f3de71dada5853035ba0081401aad197be` reproduce esas comparaciones mediante MLflow Project y conserva 52 runs y 48 modelos guardados. Los finalistas P1/P2 incluyen septiembre como evaluación retrospectiva: HGB con estación obtiene MAE 0.8620 y persistencia F1 macro 0.8695. P3 sigue usando entrenamiento y validación. Las tablas completas, los IDs y las capturas del Registry están en [resultados_mlflow_entrega2.md](reports/resultados_mlflow_entrega2.md), su JSON y el reporte PDF.

Las capturas `mlflow_01_lista`, `mlflow_02_detalle`, `mlflow_02_metricas_parametros`, `mlflow_03_artefacto` y `mlflow_04_comparacion` documentan la primera iteración. `reports/figures/entrega2/` contiene las búsquedas, artefactos y los tres modelos con su linaje de la ejecución definitiva. La interfaz es local; el profesor consulta el PDF o reproduce los comandos.

Verificaciones de la segunda entrega: 74 pruebas de unidad e integración aprobadas en Linux; descarga y reconstrucción desde un clon limpio; entorno Python 3.13.15 creado por MLflow; ingesta, entrenamiento completo y carga de los tres modelos ejecutados mediante MLflow Project. Las 52 corridas del protocolo guardaron 48 modelos con sus artefactos. Los detalles están en `reports/resultados_mlflow_entrega2.md` y su JSON.

Las verificaciones históricas incluyen notebook exploratorio con seis figuras y análisis de errores con dos figuras. Franco también documentó la reproducción de las mejoras iniciales en Windows con Python 3.13.16: 59 pruebas, regeneración de ingesta y variables, hashes, predicción, ajuste de hiperparámetros y sensibilidad. Su evidencia se conserva en el bloque `segunda_iteracion` de [resultados_mlflow.json](reports/resultados_mlflow.json) y en el [anexo histórico](reports/TC5061_Anexo_Segunda_Iteracion_Equipo45.md). La ejecución completa del MLflow Project definitivo se comprobó en Linux; CI comprueba la suite actual de 83 pruebas y la documentación en Ubuntu y Windows.

Referencias bibliográficas y justificaciones: [propuesta](references/propuesta.md).
