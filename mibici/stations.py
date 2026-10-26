"""Agrupación de estaciones para usar ``station_id`` como variable categórica en P1.

``HistGradientBoostingRegressor`` acepta variables categóricas con hasta 255 categorías y hay más
estaciones (471). ``StationGrouper`` conserva las estaciones con más horas de datos en
entrenamiento, cada una con su propia categoría, y agrupa el resto, junto con cualquier estación
no vista, en una categoría "otras". Todo se aprende solo con las filas de ``fit``, de modo que la
validación y la prueba no influyen en la codificación.

Vive en un módulo propio, y no en ``train.py``, para que el modelo guardado en MLflow se pueda
cargar desde cualquier proceso (una clase definida en ``python -m mibici.train`` se guardaría como
``__main__.StationGrouper``).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

STATION_COLUMN = "station_id"
GROUP_COLUMN = "station_group"
MAX_CATEGORIES = 255


class StationGrouper(BaseEstimator, TransformerMixin):
    """Reemplaza ``station_id`` por ``station_group``: un código por estación frecuente y "otras".

    Las estaciones se ordenan por número de filas en ``fit`` (de mayor a menor; empate por
    ``station_id``) y las primeras ``max_categories - 1`` reciben los códigos 0, 1, 2... El
    siguiente código, ``len(kept_stations_)``, es "otras". Así hay como máximo ``max_categories``
    categorías, el límite de ``HistGradientBoostingRegressor``.
    """

    def __init__(self, max_categories=MAX_CATEGORIES):
        self.max_categories = max_categories

    def fit(self, X, y=None):
        counts = X[STATION_COLUMN].value_counts()
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        kept = [station for station, _ in ordered[: self.max_categories - 1]]
        self.kept_stations_ = np.asarray(kept, dtype="int64")
        self.other_code_ = int(len(kept))
        self.n_stations_seen_ = int(len(ordered))
        return self

    def transform(self, X):
        codes = pd.Series(np.arange(len(self.kept_stations_)), index=self.kept_stations_)
        group = X[STATION_COLUMN].map(codes).fillna(self.other_code_).astype("int64")
        result = X.drop(columns=[STATION_COLUMN]).copy()
        result[GROUP_COLUMN] = group.to_numpy()
        return result

    @property
    def n_categories_(self):
        """Categorías que ve el modelo: estaciones conservadas más "otras"."""
        return self.other_code_ + 1

    @property
    def n_grouped_stations_(self):
        """Estaciones vistas en entrenamiento que quedaron dentro de "otras"."""
        return self.n_stations_seen_ - len(self.kept_stations_)
