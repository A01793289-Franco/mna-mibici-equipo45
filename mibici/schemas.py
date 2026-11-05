"""Esquemas de entrada y salida de la API de predicción por variables.

Las variables de entrada son las mismas columnas que usan los modelos de P1 y P2
(``config.P1_FEATURE_COLUMNS`` y ``config.P2_FEATURE_COLUMNS``). Los esquemas validan tipo,
rango y coherencia antes de cargar cualquier modelo; los campos extra se rechazan.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mibici import config as cfg

MAX_STATION_ID = 2**31 - 1
WEEKEND_FIRST_DAY = 5


class Variables(BaseModel):
    """Variables de calendario y de demanda reciente comunes a P1 y P2."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    hour: int = Field(ge=0, le=23, strict=True, description="Hora local del día (0 a 23)")
    weekday: int = Field(
        ge=0, le=6, strict=True, description="Día de la semana (0 lunes a 6 domingo)"
    )
    is_weekend: int = Field(ge=0, le=1, strict=True, description="1 si es sábado o domingo")
    month: int = Field(ge=1, le=12, strict=True, description="Mes (1 a 12)")
    departures_lag_1: float = Field(ge=0, description="Salidas de la estación 1 hora antes")
    departures_lag_24: float = Field(ge=0, description="Salidas 24 horas antes")
    departures_lag_168: float = Field(ge=0, description="Salidas 168 horas antes")
    departures_mean_24: float = Field(
        ge=0, description="Promedio de salidas de las 24 horas previas"
    )
    departures_mean_168: float = Field(
        ge=0, description="Promedio de salidas de las 168 horas previas"
    )
    station_id: int | None = Field(
        default=None,
        gt=0,
        le=MAX_STATION_ID,
        strict=True,
        description="Solo si el modelo champion de P2 usa la estación como variable",
    )

    @model_validator(mode="after")
    def weekend_matches_weekday(self):
        if self.is_weekend != int(self.weekday >= WEEKEND_FIRST_DAY):
            raise ValueError("is_weekend no coincide con weekday (5 y 6 son fin de semana)")
        return self


class P1Variables(Variables):
    """Entrada de P1: demanda esperada de salidas de una estación en la próxima hora.

    El modelo champion de P1 usa la estación como variable categórica, por eso es obligatoria.
    """

    station_id: int = Field(
        gt=0, le=MAX_STATION_ID, strict=True, description="Identificador de la estación"
    )


class P2Variables(Variables):
    """Entrada de P2: P1 más ocupación virtual y flujo neto rezagado."""

    virtual_occupancy: float = Field(ge=0, le=1, description="Ocupación virtual actual (0 a 1)")
    net_flow_lag_1: float = Field(description="Llegadas menos salidas 1 hora antes")
    net_flow_lag_24: float = Field(description="Llegadas menos salidas 24 horas antes")


class P1Prediction(BaseModel):
    demanda_esperada: float = Field(description="Salidas esperadas en la hora siguiente")


class P2Prediction(BaseModel):
    clase: int = Field(ge=0, le=2, description="0 normal, 1 sin bicicletas, 2 sin anclajes")
    riesgo: Literal[cfg.P2_CLASS_NAMES]
    prob_normal: float = Field(ge=0, le=1)
    prob_riesgo_sin_bicicletas: float = Field(ge=0, le=1)
    prob_riesgo_sin_anclajes: float = Field(ge=0, le=1)


class P1Response(BaseModel):
    question: Literal["P1"]
    model_uri: str
    prediction: P1Prediction


class P2Response(BaseModel):
    question: Literal["P2"]
    model_uri: str
    prediction: P2Prediction
