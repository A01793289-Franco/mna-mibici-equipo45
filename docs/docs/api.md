# API local de predicción

## Iniciar

Primero ejecuta la ingesta y el entrenamiento del [MLflow Project](getting-started.md). Conserva el servidor MLflow activo y `MLFLOW_TRACKING_URI` configurada. Desde otra terminal con el mismo entorno y la misma URI:

```text
python -m uvicorn mibici.api:app --host 127.0.0.1 --port 8000
```

- Documentación interactiva: http://127.0.0.1:8000/docs.
- Estado del proceso: http://127.0.0.1:8000/health.
- Predicción: `POST http://127.0.0.1:8000/predict`.

La respuesta de `/health` solo confirma que la API responde. No asegura que existan modelos o datos.

## Petición

```json
{
  "question": "P1",
  "station_id": 2,
  "timestamp": "2026-08-15T08:00"
}
```

`question` admite `P1` o `P2`. `station_id` es un entero positivo. La hora debe ser exacta, sin minutos ni segundos. Sin zona se interpreta en America/Mexico_City; también se admite una fecha con zona, que se convierte a esa hora local. No se aceptan campos adicionales.

Este ejemplo funciona en Linux, macOS, PowerShell y CMD:

```text
python -c "import requests; r=requests.post('http://127.0.0.1:8000/predict', json={'question':'P1','station_id':2,'timestamp':'2026-08-15T08:00'}, timeout=60); print(r.status_code, r.json())"
```

Para P2, cambia el valor de `question` a `P2`.

## Predicción con las variables del modelo

`POST /predict/p1` y `POST /predict/p2` reciben directamente los valores de las variables que usa el modelo `champion` y no leen ningún archivo local de datos, por lo que funcionan también dentro de un contenedor. Solo necesitan el servidor MLflow (`MLFLOW_TRACKING_URI`). Los esquemas de entrada y salida están en `mibici/schemas.py` y aparecen en <http://127.0.0.1:8000/docs>.

Entrada de P1 (todas obligatorias, sin campos extra):

```json
{
  "station_id": 2,
  "hour": 8,
  "weekday": 5,
  "is_weekend": 1,
  "month": 8,
  "departures_lag_1": 2.0,
  "departures_lag_24": 3.0,
  "departures_lag_168": 4.0,
  "departures_mean_24": 2.5,
  "departures_mean_168": 3.5
}
```

P2 añade `virtual_occupancy` (0 a 1), `net_flow_lag_1` y `net_flow_lag_24`. `hour` va de 0 a 23, `weekday` de 0 (lunes) a 6, `month` de 1 a 12; `is_weekend` debe coincidir con `weekday`; los rezagos y promedios de salidas no pueden ser negativos. `station_id` es obligatorio en P1, porque el modelo `champion` usa la estación como variable. En P2 es opcional y solo se necesita si el `champion` lo usa; si hace falta y no se envía, la API responde 422.

Respuesta de P1:

```json
{
  "question": "P1",
  "model_uri": "models:/mibici-p1-demanda@champion",
  "prediction": {"demanda_esperada": 2.9}
}
```

Respuesta de P2: `prediction` contiene `clase` (0 normal, 1 sin bicicletas, 2 sin anclajes), `riesgo` y las tres probabilidades `prob_*`. Un valor inválido devuelve 422 con la ubicación y el motivo, sin cargar el modelo; si no hay `champion`, 503.

## Respuesta y errores

La respuesta incluye la pregunta, la URI `models:/...@champion`, la zona del proyecto y la predicción con estación y fecha ISO en UTC. P1 devuelve `demanda_esperada`. P2 devuelve la clase, el nombre del riesgo y las tres probabilidades. Si gana la regla de persistencia, esas salidas son 0/1, no probabilidades calibradas.

| Estado HTTP | Significado |
|---|---|
| 200 | Predicción completada |
| 404 | No existe una fila de variables para esa estación y hora |
| 422 | Campos, pregunta o fecha inválidos; hora incompleta |
| 503 | No hay champion, faltan variables locales o hay filas duplicadas |

Cada petición carga el alias vigente y reutiliza `predict_hour`; la lectura Parquet filtra por estación y fecha. No entrena modelos ni recalcula variables. Si se actualiza la versión de los datos, se deben reconstruir las variables y entrenar o verificar modelos sobre esa misma versión.

## Alcance

Es una demostración local sin autenticación ni objetivos de disponibilidad. Se inicia en 127.0.0.1. No consulta inventarios reales, no genera predictores para horas todavía ausentes de las tablas y no automatiza decisiones de rebalanceo. P3 sigue disponible con `python -m mibici.predict --question P3 --split val`.
