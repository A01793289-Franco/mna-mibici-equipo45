# MiBici | Equipo 45

Propuesta de Machine Learning para apoyar la operación de MiBici en Guadalajara.

| Pregunta | Definición acordada |
|---|---|
| P1: demanda | Viajes iniciados por estación durante la siguiente hora. |
| P2: riesgo | Riesgo virtual de falta de bicicletas o anclajes al cierre de la siguiente hora. |
| P3: patrones | Tres grupos iniciales por perfil horario de uso, ubicados en un mapa. |

## Estado actual

Existen la estructura Cookiecutter, configuración, propuesta, ingesta reproducible, funciones de variables para P1-P3 y el entrenamiento de los baselines y candidatos con registro en MLflow (`mibici/train.py`). La ingesta y las variables se ejecutaron con los nueve meses seleccionados. El notebook exploratorio quedó ejecutado y las seis corridas finalizaron desde el commit `43bf339792fef5d01326aa0ca0227fdd781675ff`, con `git_dirty=false`. P1-P2 incluyen la evaluación única de septiembre; P3 compara entrenamiento y validación. Las capturas y el PDF están incluidos.

- [PDF de la propuesta y evidencia](reports/TC5061_Propuesta_Proyecto_Equipo45.pdf).
- [Resultados de las seis corridas](reports/resultados_mlflow.md) y [registro completo de métricas y parámetros](reports/resultados_mlflow.json).
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

En Windows con CMD, activar el mismo entorno con `.venv\Scripts\activate.bat`. Las dependencias directas tienen versiones fijas. No se necesita WSL ni `make`. La ejecución completa se comprobó con Python 3.13 en Linux. En Windows se comprobaron las pruebas, la regeneración de ingesta y variables y ambos `--verify`; macOS usa los comandos equivalentes indicados.

## Ingesta y variables

Con el entorno activado, en cualquiera de los tres sistemas:

```bash
python -m mibici.dataset
python -m mibici.features
python -m mibici.dataset --verify
python -m mibici.features --verify
python -m unittest discover -s tests -v
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

Recalcula la tabla de P2 **en memoria** con 25%, 50% y 75%, entrena persistencia, regresión logística y boosting con cada una, y registra un run por modelo y escenario (sufijo `_occ25`, `_occ50`, `_occ75`, parámetro `initial_occupancy`) más un run resumen. Tarda unos 3 minutos. No escribe tablas ni manifiestos (por eso no usa `features --initial-occupancy`, que sobrescribiría `data/processed/` y `feature_manifest.json`), no registra modelos y solo usa validación. Comprueba además que la tabla en memoria con 50% es idéntica a la guardada. Resultados en [reports/resultados_mlflow.md](reports/resultados_mlflow.md) y figura en `reports/figures/sensibilidad/`.

### Modelo guardado, registro y predicción

Cada run candidato (`P1_hgb_poisson_h1`, `P2_logistica_proxy_h1`, `P2_hgb_proxy_h1`) guarda su estimador con `mlflow.sklearn.log_model`, con su firma (columnas y tipos de entrada, tipo de salida) y cinco filas de ejemplo. En MLflow 3 el modelo no es una carpeta dentro de *Artifacts*: se ve en el run (pestaña *Overview*, sección *Registered models*) y en *Model registry* (modo *Model training* de la barra lateral). El baseline estacional de P1 y los agrupamientos de P3 no son estimadores predictivos y no guardan modelo.

Al terminar P1 y P2 se elige el ganador **solo con métricas de validación** y se registra en el Model Registry con el alias `champion`:

| Pregunta | Modelo registrado | Criterio |
|---|---|---|
| P1 | `mibici-p1-demanda` | menor `val_mae` entre los runs que guardan un modelo |
| P2 | `mibici-p2-riesgo` | mayor `val_f1_macro` entre los runs que guardan un modelo |

Los baselines sin modelo (estacional, persistencia) no se registran, pero se comparan: si uno supera al ganador, la versión queda con la etiqueta `supera_baselines=no: <run>` y el entrenamiento lo avisa. Cada ejecución crea una versión nueva y mueve el alias `champion` a la del ganador. Con `--no-register` se entrena sin tocar el registro. Las métricas `test_` (septiembre) nunca participan en la elección.

```bash
python -m mibici.predict --question P1 --timestamp 2026-09-15T08:00
python -m mibici.predict --question P2 --timestamp 2026-09-15T08:00 --output salida.csv
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

Las seis corridas documentadas conservan el commit de ejecución y las versiones que registraron originalmente: `data_version` `4bd1e3ec…` y `feature_version` `b588c619…`. Después, dos cambios solo de documentación actualizaron los hashes de código y, con ellos, las versiones de los manifiestos. Los docstrings de `features.py` cambiaron `feature_version`; los de `config.py` y `dataset.py` cambiaron también `data_version`. En ambos casos la reconstrucción conservó los hashes de los CSV y de los Parquet. Esta [verificación](reports/documentacion_features_verificacion.json) documenta el primer cambio; el segundo se comprueba en el historial de Git de los manifiestos, donde solo cambian hashes de código, versiones y `created_at`.

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

| Pregunta | Baseline | Candidato | Interpretación |
|---|---|---|---|
| P1 | MAE de prueba: 1.0264 | MAE de prueba: 0.8719 | El candidato reduce el error absoluto alrededor de 15.1%; aún tiene WAPE de 60.39%. |
| P2 | F1 macro de prueba: 0.8114 | F1 macro de prueba: 0.8574 | Mejora la concordancia con el proxy; no demuestra disponibilidad real. |
| P3 | K-means: silhouette 0.1407, ARI 0.5776 | Ward: silhouette 0.1232, ARI 0.3116 | K-means resulta preferible, pero los perfiles se superponen. |

Las capturas `mlflow_01_lista`, `mlflow_02_detalle`, `mlflow_02_metricas_parametros`, `mlflow_03_artefacto` y `mlflow_04_comparacion` están en `reports/figures/`. El detalle de un run se presenta en dos vistas para que se lean métricas, parámetros y etiquetas. La interfaz local no es un enlace remoto: el profesor consulta el PDF o reproduce los comandos.

Verificaciones realizadas: 59 pruebas de unidad aprobadas; verificación de hashes de ingesta y variables; reconstrucción previa con archivos idénticos; notebook sin errores y con seis figuras incrustadas. Entorno comprobado: Python 3.13.15 en Linux para todo el flujo; Python 3.13.16 en Windows para pruebas, regeneración de ingesta y variables y verificación de hashes. No se afirma haber ejecutado en macOS ni haber entrenado en Windows.

Referencias bibliográficas y justificaciones: [propuesta](references/propuesta.md).
