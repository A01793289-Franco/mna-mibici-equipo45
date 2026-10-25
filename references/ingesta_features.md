# Ingesta y feature engineering | Equipo 45

## Ejecución

Después de instalar las dependencias y activar el entorno, los comandos son iguales en Linux, macOS y Windows:

```bash
python -m mibici.dataset
python -m mibici.features
python -m mibici.dataset --verify
python -m mibici.features --verify
python -m unittest discover -s tests -v
```

Cada función de `features.py` incluye una docstring que explica su operación, su utilidad para P1, P2 o P3 y los cuidados temporales pertinentes. Este documento Markdown amplía las decisiones y los comandos de ejecución. Se conservan los comentarios de la plantilla incorporados por otros integrantes.

Los parámetros opcionales se consultan con `--help`. `--data-dir` permite usar otra carpeta local en ambos módulos. La ingesta admite `--start` y `--end` en formato `AAAA-MM-01`, con fin excluido; no acepta meses incompletos. Los cortes de entrenamiento/validación/prueba permanecen centralizados en `config.py`.

## Descarga y limpieza

`dataset.py` resuelve los enlaces publicados del rango elegido, descarga los nueve CSV y la nomenclatura, y procesa un mes a la vez en bloques. La primera ejecución requiere conexión. Las siguientes reutilizan archivos locales, verificando el hash registrado; si falta un CSV, se vuelve a descargar desde la URL guardada. `--refresh` acepta explícitamente archivos actualizados del portal y produce una nueva versión.

- Se detectan UTF-8 con/sin BOM, Windows-1252 o Latin-1 y delimitadores coma, punto y coma o tabulador. Enero utiliza Windows-1252; los otros meses seleccionados, UTF-8.
- Se normalizan acentos y variantes de columnas. Solo se escriben `trip_id`, `started_at`, `ended_at`, `origin_id` y `destination_id`.
- Fechas ISO se interpretan como año-mes-día; otras fechas locales como día/mes/año. Se conserva la zona `America/Mexico_City`. Una fecha con desplazamiento explícito se convierte a esa zona.
- Se eliminan IDs ausentes/no enteros/no positivos, fechas inválidas, finales anteriores o iguales al inicio y registros fuera del mes correspondiente. Se conservan duraciones positivas sin un recorte arbitrario por duración.
- Se elimina por ID la repetición dentro de bloques, entre bloques y entre meses, conservando la primera ocurrencia válida en orden de descarga.
- Del catálogo se conservan ID, nombre, coordenadas y capacidad positiva entera. Un ID con metadatos contradictorios detiene la ingesta. Los IDs de viajes sin catálogo se registran, sin borrarlos del conteo de P1.
- Los CSV crudos permanecen locales. Los Parquet limpios excluyen ID de usuario, género y año de nacimiento. No se publican muestras individuales.

Salidas: `data/interim/trips/AAAA-MM.parquet` y `data/interim/stations.parquet`. El identificador del viaje permanece solo en datos locales para auditar duplicados.

## Versionado

[data_manifest.json](data_manifest.json) contiene fechas, URL exactas, codificación, conteos, hashes SHA-256 de CSV y Parquet, versiones de pandas/PyArrow y hashes del código/configuración. Los paths se expresan relativos al directorio de datos; el código se identifica normalizando LF/CRLF.

`data_version` es el hash del contenido estable del manifiesto, excluyendo fecha de ejecución. Al repetirlo con los mismos archivos y código debe conservarse. Un archivo modificado falla en `--verify`. Si el proveedor reemplaza un CSV, el hash permite detectar el cambio, pero la versión anterior solo podrá reconstruirse si todavía se conserva una copia de esos bytes; Git no contiene los datos.

## Variables reutilizables

| Función de `features.py` | Salida y motivo |
|---|---|
| `load_events` | Salidas en el inicio y llegadas al terminar; evita anticipar el destino de viajes en curso. |
| `hourly_counts` | Salidas/llegadas por estación y hora, desde su primera actividad. |
| `temporal_split` | Conjuntos cronológicos; descarta horizontes que rebasan sus límites. |
| `p1_features` | Hora, día, fin de semana, mes, rezagos 1/24/168 h y medias anteriores de 24/168 h: persistencia y ciclos de demanda. |
| `virtual_occupancy` | Recorrido causal por eventos con recorte después de cada cambio, sin reiniciar entre meses o particiones. |
| `p2_features` | Variables de P1, ocupación virtual actual y flujos netos rezagados 1/24 h; etiqueta futura separada. |
| `station_profiles` | 48 medias horarias laborable/fin de semana, normalizadas para comparar formas de uso y no solo volumen. |

Las columnas predictoras autorizadas están en `P1_FEATURE_COLUMNS`, `P2_FEATURE_COLUMNS` y `P3_FEATURE_COLUMNS` de `config.py`. `station_id`, `timestamp`, `split`, objetivos, nombres y coordenadas son llaves/metadatos; **no se deben pasar automáticamente todas las columnas a un modelo**.

P1 escribe `p1_hourly.parquet` con `target_departures`. P2 escribe `p2_hourly.parquet` con `target_risk`: 0 normal, 1 riesgo sin bicicletas, 2 riesgo sin anclajes. Ambos incluyen `split` y descartan la historia inicial incompleta. El inventario futuro se utiliza únicamente para construir la etiqueta, nunca como predictor.

P3 escribe `p3_train.parquet`, `p3_val.parquet` y `p3_test.parquet`. Cada perfil se calcula solo en su ventana, excluye el primer día parcial y exige al menos 14 días completos, ambas clases de día y actividad no nula. Las coordenadas sirven para mapas, no son dimensiones de clustering. Los modelos de agrupación utilizan entrenamiento y validación, como se documenta en los resultados de MLflow.

## Supuestos y limitaciones

Se supone operación continua después de la primera actividad observada dentro de meses completamente descargados. Así se completan horas con cero; no se puede distinguir una estación cerrada, una falla del registro y ausencia real de viajes. No se emplea la última actividad futura para decidir dónde terminar una estación. La cobertura y los perfiles se evalúan retrospectivamente dentro de cada ventana.

El catálogo posterior es estático. Las estaciones sin capacidad conocida se excluyen de P2, y aquellas sin coordenadas de los perfiles destinados a mapas. P1 conserva estaciones observadas aunque falten en catálogo. Las llegadas de viajes iniciados antes del periodo no están disponibles. El estado virtual parte de un supuesto, omite rebalanceos y no representa inventario real. El manifiesto registra cuántos eventos obligan a recortar el estado fuera de capacidad.

Para sensibilidad, `python -m mibici.features --initial-occupancy 0.25` reconstruye las salidas y el manifiesto con ese escenario; `0.75` permite el otro contraste. Estas opciones sobrescriben la versión local de variables. Para volver al escenario de la propuesta, ejecutar el comando sin argumentos. La ocupación inicial queda registrada en el manifiesto.

## Evidencia de ejecución

[feature_manifest.json](feature_manifest.json) liga la versión de origen, el código, columnas predictoras, filas por conjunto, clases, exclusiones y hashes de las tablas. [La verificación de reproducción](../reports/ingesta_features_verificacion.json) documenta dos ejecuciones y las comprobaciones automáticas.

Los datos y Parquet están excluidos de Git; solo se publican código, manifiestos, conteos y pruebas sintéticas. El entrenamiento y la evaluación ya se ejecutaron con seis runs reales en MLflow. El notebook exploratorio está ejecutado, las capturas están en reports/figures/ y los resultados en reports/resultados_mlflow.md. Las condiciones publicadas del portal se documentan en references/condiciones_datos.md.

### Trazabilidad de la documentación

El hash de `features.py` incluye su documentación. Añadir docstrings actualiza `features_sha256` y `feature_version`, aunque las transformaciones sean las mismas. Se reconstruyeron las tablas y se verificó que los cinco Parquet conservan filas y SHA-256 idénticos. El [registro de verificación](../reports/documentacion_features_verificacion.json) relaciona ambas versiones.

Los resultados históricos de MLflow siguen vinculados al commit `43bf339792fef5d01326aa0ca0227fdd781675ff` y a la versión que usaron. Esa revisión de Git conserva el código y los manifiestos correspondientes. El manifiesto actual identifica el módulo con docstrings; no reemplaza los metadatos de las corridas históricas.

## Documentación de módulos y funciones

| Archivo | Elemento | Función |
|---|---|---|
| mibici/config.py | `(módulo)` | Configuración acordada para la propuesta del equipo 45. |
| mibici/config.py | `data_path` | Resuelve una ruta de datos centralizada para un directorio local alternativo. |
| mibici/config.py | `create_directories` | Crea las carpetas locales de la plantilla sin descargar datos. |
| mibici/dataset.py | `(módulo)` | Descarga, limpia y versiona los archivos mensuales de MiBici. |
| mibici/dataset.py | `sha256_file` | Calcula el hash por bloques, sin cargar el archivo completo. |
| mibici/dataset.py | `canonical_hash` | Identifica contenido JSON con un orden independiente del sistema operativo. |
| mibici/dataset.py | `source_hash` | Identifica código normalizando LF/CRLF para compartir versiones entre sistemas. |
| mibici/dataset.py | `write_json` | Publica un manifiesto completo mediante reemplazo atómico. |
| mibici/dataset.py | `http_session` | Crea una sesión identificable con reintentos para fallas transitorias. |
| mibici/dataset.py | `CSVLinks` | Extrae enlaces CSV del portal, sin fijar los identificadores de cada mes. |
| mibici/dataset.py | `discover_sources` | Resuelve todos los meses completos solicitados; falla si falta alguno. |
| mibici/dataset.py | `download_file` | Descarga atómicamente y rechaza cambios respecto de la versión registrada. |
| mibici/dataset.py | `csv_format` | Detecta UTF-8, Windows-1252 o Latin-1 y el delimitador de cada archivo. |
| mibici/dataset.py | `column_mapping` | Normaliza acentos, espacios y variantes de las columnas necesarias. |
| mibici/dataset.py | `local_dates` | Interpreta fechas locales: ISO o día/mes/año, y conserva zona horaria explícita. |
| mibici/dataset.py | `normalize_trips` | Conserva viajes válidos únicos; elimina atributos personales antes de escribir. |
| mibici/dataset.py | `clean_month` | Limpia por bloques y escribe un Parquet mensual con esquema fijo. |
| mibici/dataset.py | `clean_stations` | Normaliza catálogo y descarta capacidades/coordenadas inválidas; detecta IDs ambiguos. |
| mibici/dataset.py | `verify_manifest` | Comprueba todos los archivos crudos y limpios antes de reutilizar la versión. |
| mibici/dataset.py | `ingest` | Reconstruye meses completos y publica una versión verificable de datos sin muestras personales. |
| mibici/dataset.py | `main` | Expone ingesta, actualización explícita y verificación desde la terminal. |
| mibici/features.py | `(módulo)` | Construye tablas reproducibles para P1-P3 sin ajustar modelos ni usar futuro en predictores. |
| mibici/features.py | `local_time` | Convierte un límite de calendario a la zona horaria local de MiBici. |
| mibici/features.py | `load_events` | Lee un mes a la vez y agrega eventos simultáneos; llegadas solo al finalizar el viaje. |
| mibici/features.py | `hourly_counts` | P1-P3: completa horas tras la primera actividad, suponiendo operación continua posterior. |
| mibici/features.py | `temporal_split` | Asigna P1-P2 por tiempo y excluye horizontes que rebasan los límites del conjunto. |
| mibici/features.py | `p1_features` | P1: calendario conocido, rezagos y medias desplazadas; objetivo separado de los predictores. |
| mibici/features.py | `virtual_occupancy` | P2: simula por evento con recorte y consulta el estado estrictamente anterior a cada límite. |
| mibici/features.py | `p2_features` | P2: añade estado virtual actual y flujos pasados; la ocupación futura solo define la etiqueta. |
| mibici/features.py | `station_profiles` | P3: compara la forma de 48 medias horarias sin que domine el volumen total. Excluye el primer día parcial, la cobertura insuficiente y los perfiles nulos. |
| mibici/features.py | `verify_features` | Comprueba versión de origen, código y hashes para detectar variables desactualizadas. |
| mibici/features.py | `build_features` | Genera P1, P2 y perfiles P3 por partición desde los Parquet verificados de ingesta. |
| mibici/features.py | `main` | Expone construcción y comprobación de variables en Windows, macOS y Linux. |
| tests/test_data_features.py | `(módulo)` | Verificaciones de calidad, reproducción y disponibilidad temporal con datos sintéticos. |

## Comandos opcionales del Makefile

| Comando | Función |
|---|---|
| `make requirements` | Instala las dependencias de Python. |
| `make clean` | Elimina archivos de Python compilados y carpetas de caché. |
| `make lint` | Comprueba el formato con las herramientas de la plantilla. |
| `make format` | Aplica isort y black al módulo. |
| `make create_environment` | Conserva el comando de virtualenvwrapper de la plantilla; el README explica la alternativa con venv. |
| `make data` | Ejecuta la ingesta reproducible. |
| `make features` | Construye las tablas para P1-P3. |
| `make verify` | Verifica hashes y versiones de datos y variables, sin ejecutar pruebas. |
| `make test` | Ejecuta las pruebas unitarias con datos sintéticos. |
| `make train` | Ejecuta `make verify` y, si pasa, entrena P1-P3 en validación y registra los runs en MLflow. |
| `make help` | Muestra todos los objetivos anteriores con su descripción. |

`make train` no usa `--final-test`. La evaluación de septiembre se ejecuta a mano y una sola vez, según el [protocolo](protocolo_experimento.md).
