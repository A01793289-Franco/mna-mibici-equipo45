"""
P1 - Predicción de demanda por estación para la siguiente hora.

Entrena un HistGradientBoostingRegressor utilizando las variables
generadas por el pipeline de feature engineering y evalúa el desempeño
sobre el conjunto de validación.
"""

import pandas as pd

from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.metrics import root_mean_squared_error
from sklearn.metrics import mean_absolute_error
from sklearn.metrics import root_mean_squared_error
from sklearn.metrics import r2_score


FEATURES = [
    "hour",
    "weekday",
    "is_weekend",
    "month",
    "departures_lag_1",
    "departures_lag_24",
    "departures_lag_168",
    "departures_mean_24",
    "departures_mean_168",
]

TARGET = "target_departures"

def wape(y_true, y_pred):
    """
    Weighted Absolute Percentage Error (WAPE).

    Mide el error absoluto total respecto al volumen total observado.
    Es adecuada para series con muchos ceros, como la demanda de MiBici.
    """
    denominator = y_true.abs().sum()

    if denominator == 0:
        return float("nan")

    return (y_true - y_pred).abs().sum() / denominator


def main():
    """Ejecuta entrenamiento y evaluación inicial del modelo P1."""

    # Cargar dataset generado por features.py
    data = pd.read_parquet("data/processed/p1_hourly.parquet")

    # Separación temporal definida en el pipeline
    train = data[data["split"] == "train"]
    val = data[data["split"] == "val"]

    # Variables predictoras y objetivo
    X_train = train[FEATURES]
    y_train = train[TARGET]

    X_val = val[FEATURES]
    y_val = val[TARGET]

    # Modelo candidato definido en la propuesta
    model = HistGradientBoostingRegressor(
        loss="poisson",
        random_state=42,
    )

    # Entrenamiento
    model.fit(X_train, y_train)

    # Predicciones
    preds = model.predict(X_val)

    # Métricas de evaluación
    mae = mean_absolute_error(y_val, preds)
    rmse = root_mean_squared_error(y_val, preds)
    r2 = r2_score(y_val, preds)
    wape_score = wape(y_val, preds)

    print("\nResultados de validación")
    print("-" * 30)
    print(f"MAE:  {mae:.4f}")
    print(f"RMSE: {rmse:.4f}")
    print(f"R²:   {r2:.4f}")
    print(f"WAPE: {wape_score:.4f}")


if __name__ == "__main__":
    main()