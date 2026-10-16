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

P3 escribe `p3_train.parquet`, `p3_val.parquet` y `p3_test.parquet`. Cada perfil se calcula solo en su ventana, excluye el primer día parcial y exige al menos 14 días completos, ambas clases de día y actividad no nula. Las coordenadas sirven para mapas, no son dimensiones de clustering. No se han entrenado agrupaciones con estas tablas.

## Supuestos y limitaciones

Se supone operación continua después de la primera actividad observada dentro de meses completamente descargados. Así se completan horas con cero; no se puede distinguir una estación cerrada, una falla del registro y ausencia real de viajes. No se emplea la última actividad futura para decidir dónde terminar una estación. La cobertura y los perfiles se evalúan retrospectivamente dentro de cada ventana.

El catálogo posterior es estático. Las estaciones sin capacidad conocida se excluyen de P2, y aquellas sin coordenadas de los perfiles destinados a mapas. P1 conserva estaciones observadas aunque falten en catálogo. Las llegadas de viajes iniciados antes del periodo no están disponibles. El estado virtual parte de un supuesto, omite rebalanceos y no representa inventario real. El manifiesto registra cuántos eventos obligan a recortar el estado fuera de capacidad.

Para sensibilidad, `python -m mibici.features --initial-occupancy 0.25` reconstruye las salidas y el manifiesto con ese escenario; `0.75` permite el otro contraste. Estas opciones sobrescriben la versión local de variables. Para volver al escenario de la propuesta, ejecutar el comando sin argumentos. La ocupación inicial queda registrada en el manifiesto.

## Evidencia y siguientes pasos

[feature_manifest.json](feature_manifest.json) liga la versión de origen, el código, columnas predictoras, filas por conjunto, clases, exclusiones y hashes de las tablas. [La verificación de reproducción](../reports/ingesta_features_verificacion.json) documenta dos ejecuciones y las comprobaciones automáticas.

Los datos y Parquet están excluidos de Git; solo se publican código, manifiestos, conteos y pruebas sintéticas. Quedan pendientes entrenamiento, evaluación y registro de baselines reales en MLflow, notebook exploratorio y capturas de la interfaz. Las condiciones de uso del portal todavía deben documentarse en la entrega final.
