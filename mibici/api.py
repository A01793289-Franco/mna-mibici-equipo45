from datetime import datetime
import json
from typing import Literal

from fastapi import FastAPI, HTTPException
from mlflow.exceptions import MlflowException
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from mibici import config as cfg
from mibici.features import local_time
from mibici.predict import PredictionError, features_table, load_champion, predict_hour
from mibici.train import REGISTERED_MODELS, configure_mlflow

app = FastAPI(title="MiBici Equipo 45", version="0.1.0")
# station_id es int32 en las tablas de variables; un valor mayor desborda el filtro de Parquet.
MAX_STATION_ID = 2**31 - 1


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
