from datetime import datetime
import json
import os
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse
from mlflow.exceptions import MlflowException
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from mibici import config as cfg
from mibici.features import local_time
from mibici.predict import PredictionError, features_table, load_champion, predict_hour
from mibici.schemas import P1Response, P1Variables, P2Response, P2Variables
from mibici.train import REGISTERED_MODELS, class_probabilities
from mibici.train import configure_mlflow as connect_mlflow

app = FastAPI(title="MiBici Equipo 45", version="0.1.0")
# station_id es int32 en las tablas de variables; un valor mayor desborda el filtro de Parquet.
MAX_STATION_ID = 2**31 - 1


def configure_mlflow():
    """Conecta con MLflow; responde 503 si no hay servidor configurado ni base local.

    Sin esta comprobación, un contenedor sin ``MLFLOW_TRACKING_URI`` intenta crear ``mlflow.db``
    y tarda minutos en fallar.
    """
    if not os.environ.get("MLFLOW_TRACKING_URI") and not cfg.MLFLOW_DB.exists():
        raise HTTPException(
            status_code=503, detail="Configura MLFLOW_TRACKING_URI para conectar con MLflow."
        )
    connect_mlflow()


@app.exception_handler(RequestValidationError)
async def invalid_request(request, error):
    """Responde 422 con ubicación, mensaje y tipo, sin devolver el valor recibido.

    El valor puede no ser serializable (por ejemplo NaN) y provocaría un error 500.
    """
    details = [
        {"loc": list(item["loc"]), "msg": item["msg"], "type": item["type"]}
        for item in error.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": details})


@app.exception_handler(ResponseValidationError)
async def invalid_prediction(request, error):
    return JSONResponse(
        status_code=503, content={"detail": "El modelo produjo una salida inválida"}
    )


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: Literal["P1", "P2"]
    station_id: int = Field(gt=0, le=MAX_STATION_ID, strict=True)
    timestamp: datetime


@app.get("/health")
def health():
    return {"status": "ok", "service": "mibici-prediction"}


@app.post("/predict")
def predict(request: PredictionRequest):
    when = local_time(request.timestamp)
    if when.minute or when.second or when.microsecond:
        raise HTTPException(
            status_code=422, detail="Indica una hora completa, sin minutos ni segundos"
        )
    try:
        configure_mlflow()
        model, columns = load_champion(request.question)
    except (PredictionError, MlflowException) as error:
        raise HTTPException(
            status_code=503, detail="El modelo champion no está disponible"
        ) from error
    needed = list(dict.fromkeys(["station_id", "timestamp", *columns]))
    try:
        frame = pd.read_parquet(
            features_table(request.question),
            columns=needed,
            filters=[("station_id", "=", request.station_id), ("timestamp", "=", when)],
        )
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=503, detail="Las variables locales no están disponibles"
        ) from error
    if frame.empty:
        raise HTTPException(status_code=404, detail="No hay variables para esa estación y hora")
    if len(frame) != 1:
        raise HTTPException(
            status_code=503, detail="La tabla contiene filas duplicadas para esa estación y hora"
        )
    result = predict_hour(request.question, when, table=frame, model=model, columns=columns)
    record = json.loads(result.to_json(orient="records", date_format="iso"))[0]
    return {
        "question": request.question,
        "model_uri": f"models:/{REGISTERED_MODELS[request.question]}@champion",
        "timezone": cfg.TIMEZONE,
        "prediction": record,
    }


def load_model_or_503(question):
    """Carga el champion de la pregunta; si no está disponible responde 503."""
    try:
        configure_mlflow()
        return load_champion(question)
    except (PredictionError, MlflowException) as error:
        raise HTTPException(
            status_code=503, detail="El modelo champion no está disponible"
        ) from error


def variables_frame(variables, columns):
    """Una fila con las columnas que pide la firma del modelo; 422 si falta alguna."""
    values = variables.model_dump()
    missing = [name for name in columns if values.get(name) is None]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"El modelo champion requiere variables ausentes en la petición: {missing}",
        )
    return pd.DataFrame([{name: values[name] for name in columns}])


@app.post("/predict/p1", response_model=P1Response)
def predict_p1(variables: P1Variables):
    """Demanda esperada de salidas a partir de las variables de P1."""
    model, columns = load_model_or_503("P1")
    frame = variables_frame(variables, columns)
    return {
        "question": "P1",
        "model_uri": f"models:/{REGISTERED_MODELS['P1']}@champion",
        "prediction": {"demanda_esperada": float(model.predict(frame)[0])},
    }


@app.post("/predict/p2", response_model=P2Response)
def predict_p2(variables: P2Variables):
    """Clase de riesgo y probabilidades a partir de las variables de P2."""
    model, columns = load_model_or_503("P2")
    frame = variables_frame(variables, columns)
    probabilities = class_probabilities(model, frame)[0]
    label = int(probabilities.argmax())
    return {
        "question": "P2",
        "model_uri": f"models:/{REGISTERED_MODELS['P2']}@champion",
        "prediction": {
            "clase": label,
            "riesgo": cfg.P2_CLASS_NAMES[label],
            **{f"prob_{name}": float(p) for name, p in zip(cfg.P2_CLASS_NAMES, probabilities)},
        },
    }
