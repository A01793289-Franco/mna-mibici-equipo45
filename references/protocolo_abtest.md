# Protocolo de comparación de versiones de P1

## Alcance

Se aplica a `mibici-p1-demanda`. A y B se recuperan del mismo Model Registry mediante los alias `champion` y `challenger`, o mediante versiones explícitas. Primero se resuelven los alias; toda la inferencia utiliza las URI numéricas inmutables `models:/nombre/version`. No se promueve ningún modelo automáticamente.

Es el A/B offline solicitado en la actividad: ambas versiones predicen exactamente las mismas filas. No es un experimento con asignación aleatoria de tráfico o usuarios. Septiembre ya se observó en entregas previas y en el paso 4; por ello se declara evaluación retrospectiva y no prueba final independiente.

## Datos y separación temporal

- A: HGB con estación, semilla 42 y parámetros establecidos en `config.HGB_DEFAULTS`, ajustado con enero-junio.
- B: la alternativa de Franco con el mismo algoritmo, variables, semilla y parámetros, ajustada con enero-agosto mediante `train_window=train_val`.
- Evaluación común: todas las filas `split=test` de septiembre, sin muestreo, ordenadas por fecha y estación.
- Se comprueban claves únicas, calendario de particiones y que el horizonte objetivo no cruce los cortes. Ninguna versión puede acreditar un fin de entrenamiento posterior al inicio de septiembre.
- Las versiones y la evaluación deben compartir las versiones de datos y variables. Se registran los hashes de la tabla Parquet y de las filas de evaluación, las firmas, las versiones numéricas, los runs y los commits.
- Las estaciones conocidas/nuevas se definen respecto al entrenamiento original de A, para que el segmento sea el mismo al comparar ambas versiones.

## Métricas e incertidumbre

MAE es la métrica principal de P1. RMSE, WAPE global y R² complementan la interpretación. WAPE se registra como proporción; si la demanda total es cero se informa como no definido. No se convierten valores no definidos en cero.

Se calcula la diferencia pareada `MAE_A - MAE_B`: un valor positivo favorece B. El intervalo de confianza del 95% se estima con 5,000 réplicas de bootstrap circular de bloques de siete días, semilla 42. Se remuestrean conjuntamente los errores de A y B de todas las estaciones de cada día; las sumas de errores se dividen entre las filas remuestreadas. Así se conservan la dependencia dentro del día y bloques de la secuencia semanal, sin tratar 338,690 filas como observaciones independientes.

El intervalo es condicional al único mes disponible; con 30 días hay pocos bloques semanales efectivos. No demuestra que la ventaja persista fuera de septiembre ni permite inferir causas del drift.

## Regla de decisión

Se recomienda B solamente cuando se cumplen las cuatro condiciones:

1. Su MAE global es menor.
2. El límite inferior del IC95 de `MAE_A - MAE_B` es mayor que cero.
3. Su RMSE global no aumenta.
4. Su MAE en estaciones nuevas respecto a A no aumenta, si ese segmento existe.

De lo contrario se recomienda mantener A. La regla se fija antes de ejecutar el nuevo comparador, con conocimiento de las métricas globales ya publicadas en el README; no se presenta como una preregistración anterior a toda observación de septiembre. No se ajustan hiperparámetros según esta comparación.

## Continuous Training

Monitorear calidad y drift mensualmente. Las alertas abren una revisión: no ordenan reentrenar ni promover por sí mismas. Si cambian las estaciones o la demanda y se observa degradación relevante, entrenar una alternativa solo con datos disponibles antes del siguiente periodo de evaluación. Aplicar las métricas y controles anteriores en un nuevo periodo, revisar el resultado y conservar la versión anterior para reversión. El umbral de costo operativo requiere objetivos del operador y no se inventa en este ejercicio.

## Reproducción

Con los datos verificados y las dos versiones ya registradas:

```text
python -m mibici.abtest
python -m mibici.abtest --champion-version 1 --challenger-version 2
```

`MLFLOW_TRACKING_URI` selecciona el servidor o base local; también se acepta `--tracking-uri`. `--output-dir` permite conservar una reproducción separada. La salida contiene `resultados.json`, `resultados.md` y `comparacion.png`; MLflow registra parámetros, métricas, el dataset de evaluación como metadatos y esos artefactos. No se publican predicciones por fila, datos ni bases en Git.

Referencias: [MLflow Model Registry](https://mlflow.org/docs/latest/ml/model-registry/workflow/) y [bootstrap de series temporales](https://arch.readthedocs.io/en/latest/bootstrap/timeseries-bootstraps.html).
