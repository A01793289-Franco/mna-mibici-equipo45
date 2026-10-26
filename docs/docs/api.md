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
