# MiBici | Equipo 45

Propuesta de Machine Learning para apoyar la operación de MiBici en Guadalajara.

| Pregunta | Definición acordada |
|---|---|
| P1: demanda | Viajes iniciados por estación durante la siguiente hora. |
| P2: riesgo | Riesgo virtual de falta de bicicletas o anclajes al cierre de la siguiente hora. |
| P3: patrones | Tres grupos iniciales por perfil horario de uso, ubicados en un mapa. |

## Estado actual

Existen la estructura Cookiecutter, configuración, propuesta, ingesta reproducible, funciones de variables para P1-P3 y el entrenamiento de los baselines y candidatos con registro en MLflow (`mibici/train.py`). La ingesta y las variables se ejecutaron con los nueve meses seleccionados. Faltan la evidencia final (capturas), el notebook exploratorio y la evaluación única sobre septiembre.

- [ML Canvas editable](references/ml_canvas.md).
- [ML Canvas en PDF](references/Machine%20Learning%20Canvas.pdf).
- [Propuesta: datos, partición, pipelines, modelos y métricas](references/propuesta.md).
- [Arquitectura y justificación](references/arquitectura.md).
- [Diagrama editable](references/arquitectura.svg).
- [Ingesta y variables: decisiones, comandos y limitaciones](references/ingesta_features.md).
- [Manifiesto de datos](references/data_manifest.json) y [manifiesto de variables](references/feature_manifest.json).

## Datos y configuración

Fuente: [datos abiertos de MiBici](https://www.mibici.net/es/datos-abiertos/). Se proponen nueve meses completos, enero-septiembre de 2026, y el catálogo de septiembre.

Entrenamiento: enero-junio; validación: julio-agosto; prueba: septiembre. Los intervalos incluyen inicio y excluyen fin. Las variables de cada hora solo podrán usar eventos anteriores al momento de predecir.

La ingesta obtuvo **3,362,065 registros originales y 3,358,273 viajes válidos** en nueve meses: 3,034 registros inválidos y 758 duplicados descartados. Se observaron 471 IDs de estación; el catálogo contiene 480 estaciones válidas. Los IDs 405 y 407 no aparecen en él. Son cifras del rango descargado, no contadores globales del portal.

Las salidas contienen 2,556,542 filas de P1 y 2,551,458 de P2; los perfiles P3 incluyen 397 estaciones de entrenamiento, 468 de validación y 468 de prueba. Ver versiones, conteos y hashes en los manifiestos. La propuesta documenta las limitaciones del catálogo posterior y del riesgo simulado.

`mibici/config.py` centraliza rutas, fuentes, fechas, semilla, horizontes, umbrales y parámetros de clustering. Los próximos módulos deberán importar esos valores.

## Estructura actual

```text
mibici/
  __init__.py
  config.py
  dataset.py
  features.py
references/
  Machine Learning Canvas.pdf
  ml_canvas.md
  propuesta.md
  arquitectura.md
  arquitectura.svg
  ingesta_features.md
  data_manifest.json
  feature_manifest.json
notebooks/
models/
reports/figures/
tests/
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

En Windows con CMD, activar el mismo entorno con `.venv\Scripts\activate.bat`. Las dependencias directas tienen versiones fijas. No se necesita WSL ni `make`. La ejecución se comprobó con Python 3.13 en Linux; los otros sistemas usan los comandos equivalentes indicados.

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
python -m mibici.train --question all      # P1, P2 y P3 (también: --question P1, P2 o P3)
python -m mlflow ui --backend-store-uri sqlite:///mlflow.db
```

La interfaz queda en <http://127.0.0.1:5000>, experimento `mibici-equipo45`. `python -m mibici.train_p1` sigue funcionando y equivale a `--question P1`.

| Run | Pregunta | Modelo | Métricas principales (validación) |
|---|---|---|---|
| `P1_estacional_h1` | P1 | Baseline: misma estación y hora de la semana anterior | `val_mae`, `val_rmse`, `val_wape` |
| `P1_hgb_poisson_h1` | P1 | `HistGradientBoostingRegressor` con pérdida de Poisson | `val_mae`, `val_rmse`, `val_wape` |
| `P2_logistica_proxy_h1` | P2 | Baseline: regresión logística balanceada de tres clases | `val_f1_macro`, `val_balanced_accuracy`, `val_ap_macro` |
| `P2_hgb_proxy_h1` | P2 | `HistGradientBoostingClassifier` balanceado | `val_f1_macro`, `val_balanced_accuracy`, `val_ap_macro` |
| `P3_kmeans_perfil48` | P3 | Baseline: K-means con k=3 | `train_silhouette`, `train_davies_bouldin`, `val_ari` |
| `P3_ward_perfil48` | P3 | Agrupamiento jerárquico Ward con k=3 | `train_silhouette`, `train_davies_bouldin`, `val_ari` |

Cada run registra:

- **Etiquetas:** `equipo`, `pregunta` (P1, P2 o P3), `tipo` (baseline o candidato), `git_commit` y `git_dirty`.
- **Parámetros:** semilla, fechas de partición, horizonte, `data_version`, `feature_version`, columnas usadas, filas por conjunto y los parámetros del modelo.
- **Métricas:** con prefijo `val_` (y `train_` en P3). Una métrica no definida, por ejemplo la AP de una clase sin ejemplos, no se registra y queda anotada en la etiqueta `metricas_no_definidas`.
- **Artefactos:** figura de cada run (demanda por hora, matriz de confusión, o mapa y perfiles de los grupos) y, en P3, la tabla de grupos por estación. Las figuras también se guardan en `reports/figures/`.

Para que el commit registrado describa el código exacto, hay que correr el entrenamiento después de confirmar los cambios (`git_dirty` debe ser `false`). La prueba (septiembre) no se usa por defecto: `--final-test` añade las métricas `test_` y debe ejecutarse una sola vez, cuando las decisiones ya estén fijas. `mlflow.db` y `mlartifacts/` están en `.gitignore`: cada integrante reproduce los runs en su máquina.

## Flujo de trabajo propuesto

- Ramas `feat/descripcion`, `fix/descripcion`, `docs/descripcion` o `chore/descripcion`.
- Commits `tipo: descripción`, por ejemplo `feat: agrega ingesta mensual`.
- Cada cambio entra mediante Pull Request revisado por otro integrante.
- Proteger `main` y exigir revisión: configuración pendiente del administrador.
- Cada uno de los cuatro integrantes debe abrir y revisar al menos un PR. Nombres y roles quedan pendientes de confirmación del equipo.

## Reproducibilidad y privacidad

Los manifiestos versionan URL, SHA-256, código y conteos sin publicar archivos de datos. La versión de variables referencia la versión de ingesta. Cada futuro run deberá registrar esas versiones, commit, pregunta, fechas, semilla, modelo, parámetros, métricas con prefijo y al menos un artefacto.

`.gitignore` excluye datos, modelos serializados, `mlruns`, `mlartifacts`, la base local de MLflow y archivos de entorno. MIT cubre el código; las condiciones de uso de los datos deberán documentarse como indica la propuesta.

## Pendientes de la entrega completa

1. Ejecutar `python -m mibici.train --question all` con el código ya confirmado en Git y revisar los resultados.
2. Crear el notebook exploratorio.
3. Capturar lista, detalle, artefacto y comparación de runs en la interfaz de MLflow.
4. Completar participación de cuatro integrantes, revisiones y protección de `main`.
5. Documentar condiciones de uso de las fuentes, integrar el PDF final y ajustar el nombre del repositorio.

Referencias bibliográficas y justificaciones: [propuesta](references/propuesta.md).
