# Pruebas y CI

## Comprobación local

Con las dependencias instaladas:

```text
python -m pip install -r requirements-validation.txt
python -m flake8 mibici tests
python -m pytest -v
python -m mkdocs build --strict -f docs/mkdocs.yml
```

La suite usa datos sintéticos y almacenes temporales de MLflow. No descarga viajes ni requiere un servidor de tracking externo. Las pruebas de la API usan `TestClient` y comprueban predicciones, fechas, datos ausentes y errores de entrada.

PyTest ejecuta también las pruebas escritas con `unittest`. Las pruebas nuevas usan fixtures de `tests/conftest.py`:

| Archivo | Qué comprueba |
|---|---|
| `test_dataset_utils.py` | Mapeo de cabeceras, detección de codificación y separador, hash canónico y rutas de datos, con casos límite |
| `test_hourly_counts.py` | Agregación horaria, horas sin eventos, alta de estaciones y límite final del periodo |
| `test_reproducibility.py` | Dos entrenamientos con la misma semilla: predicciones, métricas en MLflow, modelos guardados y CSV de P3 idénticos |
| `test_security.py` | Exclusión de secretos, `.env.example`, versiones fijas y entradas inválidas o extremas en la API |
| `test_validation.py` | Que la validación con DeepChecks apruebe datos limpios y detecte nulos, duplicados, rangos, tipos y partición incorrecta |

Las pruebas de reproducibilidad activan early stopping en el boosting, porque solo así la semilla interviene en su entrenamiento. Una prueba de control comprueba que otra semilla sí cambia el resultado. Se excluyen las métricas de tiempo.

Para verificar los datos reales y modelos generados en tu máquina:

```text
python -m mibici.dataset --verify
python -m mibici.features --verify
python -m mibici.validation
python -m mibici.verify_registry --question all
```

## Validación de datos con DeepChecks

`python -m mibici.validation` lee las tablas de `data/processed` y ejecuta tres suites por conjunto (P1, P2 y P3):

| Suite | Bloqueante | Checks |
|---|---|---|
| Integridad | Sí | Tipos esperados (check propio), tipos mezclados, nulos, duplicados por fila y por estación-hora, columnas constantes y reglas de dominio: horas, días y meses coherentes con `timestamp`, conteos no negativos, ocupación virtual en [0, 1], clases de riesgo válidas, perfiles P3 normalizados, coordenadas en Guadalajara y `split` igual a los cortes de `config.py` |
| Partición | Sí | Sin fechas compartidas entre entrenamiento y validación o prueba; sin clases nuevas de P2 |
| Drift | No | Drift de variables y del objetivo en una muestra de 100,000 filas con la semilla del proyecto |

El drift se reporta pero no detiene la validación, porque enero-junio, julio-agosto y septiembre tienen estacionalidad esperada. `month` se excluye del drift. Comparar distribuciones de septiembre no evalúa modelos, así que no consume el uso único del conjunto de prueba.

El comando termina con código 1 si falla una suite bloqueante. La evidencia queda en `reports/deepchecks/resumen.json` y `resumen.md`. `--html` añade un reporte por suite en `reports/deepchecks/html`, fuera de Git porque los de drift pesan más de 40 MB.

deepchecks 0.19.1, la última versión publicada, es anterior a numpy 2, pandas 3 y scikit-learn 1.9. `mibici.validation` restituye tres nombres eliminados (`np.Inf`, `DataFrame.applymap` y el scorer `max_error`) antes de importarlo. `MultivariateDrift` queda fuera por ser incompatible con scikit-learn 1.9. La validación también desactiva el aviso de versión de deepchecks, que envía un identificador anónimo a su servidor. Sus dependencias están en `requirements-validation.txt` para no alterar el entorno de entrenamiento.

## Seguridad

- **Secretos:** `.gitignore` excluye `.env`, `.env.*`, `mlflow.db`, `mlartifacts/`, datos y modelos serializados; `.env.example` sí se versiona y solo contiene `MLFLOW_TRACKING_URI` sin valor. El código lee variables con `os.environ`. Una prueba busca llaves privadas, tokens y credenciales en los archivos versionados.
- **Dependencias:** las versiones directas son exactas. `make security` y CI ejecutan `pip-audit` sobre el entorno instalado y `bandit` sobre `mibici` (severidad media o alta).
- **Entradas:** la API valida con Pydantic, sin campos extra, y limita `station_id` a enteros entre 1 y 2^31 - 1, el rango de la columna `int32`. Los errores internos devuelven mensajes genéricos sin rutas ni detalles del servidor.

Vulnerabilidades revisadas e ignoradas en `pip-audit`, a revisar si cambia el uso:

| Paquete | Identificadores | Por qué no aplica |
|---|---|---|
| mlflow 3.16.1 | CVE-2026-53995, CVE-2026-115886 | Afectan al servidor de tracking expuesto en red. El proyecto usa SQLite local y la interfaz solo en `127.0.0.1` |
| mlflow 3.16.1 | CVE-2026-116691 | Afecta a `mlflow.crewai.autolog`, que no se usa |
| setuptools 80.10.2 | PYSEC-2026-3447, GHSA-xmj3-9gf7-h52w | Versión fijada por deepchecks. Afecta la construcción de sdist y la instalación heredada de wheels, que el proyecto no usa |

Actualizar a mlflow 3.17.2 elimina las tres primeras, pero exige comprobar que los modelos registrados con 3.16.1 siguen cargando. Queda pendiente.

`bandit` solo reporta avisos de severidad baja por el uso de `subprocess` para leer el commit de Git con argumentos fijos.

## GitHub Actions

El archivo `.github/workflows/ci.yml` se ejecuta en cada Pull Request y en los pushes de `main` y de la rama de integración. También permite una ejecución manual. La matriz usa Ubuntu y Windows con Python 3.13.15.

Cada trabajo de calidad instala `requirements-validation.txt`, ejecuta lint, corre PyTest y construye MkDocs en modo estricto. El trabajo `security` corre en Ubuntu con `pip-audit` y `bandit`. Si falla un comando, el trabajo queda en rojo. No se ignoran errores y no se descargan datos reales ni se guardan modelos de producción en el repositorio.

El token del trabajo solo tiene permiso de lectura del contenido. Las acciones de checkout y preparación de Python están fijadas a commits de sus repositorios oficiales.

[Consultar las ejecuciones de CI](https://github.com/A01793289-Franco/mna-mibici-equipo45/actions/workflows/ci.yml).

Las verificaciones automáticas complementan la revisión del PR. La fusión y la participación de los integrantes se comprueban en el historial de GitHub.
