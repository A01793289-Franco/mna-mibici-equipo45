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
| `test_repository_security.py` | Detección de secretos borrados del historial, archivos privados, redacción de resultados y exclusión de columnas personales |
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

El escaneo del repositorio y el análisis de código se pueden ejecutar en cualquier sistema desde la raíz:

```text
python -m mibici.security --history --output reports/security/repositorio.json
python -m bandit -c pyproject.toml -r mibici -ll
```

El escáner incluye los archivos actuales no excluidos por Git y los blobs del historial disponible. Detecta patrones de credenciales y archivos privados, incluso si se borraron después. El reporte registra rutas y categorías, nunca los valores coincidentes. Inspecciona texto de hasta 5 MB por archivo; el JSON declara los textos mayores omitidos. Los binarios no se inspeccionan como texto, pero se revisa su nombre contra la política de datos, bases, llaves y modelos. Es un control básico por patrones, complementario a la revisión humana.

El CI de seguridad obtiene el historial completo con `fetch-depth: 0`. Las pruebas de privacidad confirman que columnas como correo, nombre, identificador de usuario y año de nacimiento se descartan al normalizar los viajes.

La organización y los comandos por grupo están en [tests/README.md](https://github.com/A01793289-Franco/mna-mibici-equipo45/blob/main/tests/README.md). La suite completa sigue ejecutándose con `python -m pytest -v`.

- **Secretos:** `.gitignore` excluye `.env`, `.env.*`, `mlflow.db`, `mlartifacts/`, datos y modelos serializados; `.env.example` sí se versiona y solo contiene `MLFLOW_TRACKING_URI` sin valor. El código lee variables con `os.environ`. Una prueba busca llaves privadas, tokens y credenciales en los archivos versionados.
- **Dependencias:** las versiones directas son exactas. `make security` y CI ejecutan `pip-audit` sobre el entorno instalado y `bandit` sobre `mibici` (severidad media o alta).
- **Entradas:** la API valida con Pydantic, sin campos extra, y limita `station_id` a enteros entre 1 y 2^31 - 1, el rango de la columna `int32`. Los errores internos devuelven mensajes genéricos sin rutas ni detalles del servidor.

Se actualizó MLflow de 3.16.1 a **3.17.2** para corregir los avisos de esa dependencia. La suite completa aprobó y los modelos históricos de P1-P3 se cargaron con el cliente actualizado, reproduciendo cinco ejemplos por modelo. La comprobación utiliza una copia local del Registry histórico. Los resultados quedan en [la evidencia de seguridad](https://github.com/A01793289-Franco/mna-mibici-equipo45/blob/main/reports/security/README.md).

Fuentes de la actualización: [aviso oficial de FileStore](https://github.com/advisories/GHSA-wqmh-qccw-pqwf), [aviso de scorers](https://github.com/mlflow/mlflow/security/advisories/GHSA-2wqp-q3c6-ccj5) y [aviso de CrewAI](https://github.com/mlflow/mlflow/security/advisories/GHSA-j7qq-vr8c-xvw3).

La auditoría sin exclusiones del entorno completo todavía devuelve tres entradas de `setuptools`, correspondientes a dos avisos distintos. Su código de salida es 1; ese resultado se conserva junto con las excepciones aceptadas para el entorno de validación:

| Paquete | Identificadores | Alcance y control |
|---|---|---|
| setuptools 80.10.2 | PYSEC-2026-3447 | DeepChecks 0.19.1 usa `pkg_resources`, eliminado en setuptools 81. Se mantiene la versión compatible en `requirements-validation.txt`; CI instala dependencias externas solo desde wheels con pip moderno, sin construir sdist. |
| setuptools 80.10.2 | GHSA-xmj3-9gf7-h52w | El aviso afecta la instalación heredada de wheels mediante setuptools. Se usa instalación moderna de pip y dependencias de PyPI; no se llama a `Wheel.install_as_egg`. |

La lista de CI y `make security` solo acepta esos dos identificadores. Cualquier aviso nuevo hace fallar la auditoría. Esta aceptación corresponde al entorno de validación y debe revisarse al actualizar DeepChecks o modificar la instalación. [Aviso oficial sobre la instalación heredada](https://github.com/pypa/setuptools/security/advisories/GHSA-xmj3-9gf7-h52w).

Bandit reporta seis avisos bajos asociados al uso de `subprocess` para consultar Git, sin shell. El análisis bloqueante de severidad media o alta devuelve cero hallazgos. La revisión de secretos informa rutas y tipos, sin imprimir las cadenas detectadas.

## GitHub Actions

El archivo `.github/workflows/ci.yml` se ejecuta en cada Pull Request y en los pushes de `main` y de la rama de integración. También permite una ejecución manual. La matriz usa Ubuntu y Windows con Python 3.13.15.

Cada trabajo de calidad instala `requirements-validation.txt`, ejecuta lint, corre PyTest y construye MkDocs en modo estricto. El trabajo `security` corre en Ubuntu con el escaneo del repositorio e historial, `pip-audit` y `bandit`. Si falla un comando, el trabajo queda en rojo. No se ignoran errores y no se descargan datos reales ni se guardan modelos de producción en el repositorio.

El token del trabajo solo tiene permiso de lectura del contenido. Las acciones de checkout y preparación de Python están fijadas a commits de sus repositorios oficiales.

[Consultar las ejecuciones de CI](https://github.com/A01793289-Franco/mna-mibici-equipo45/actions/workflows/ci.yml).

Las verificaciones automáticas complementan la revisión del PR. La fusión y la participación de los integrantes se comprueban en el historial de GitHub.
