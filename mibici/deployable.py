import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin, ClusterMixin, RegressorMixin
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.neighbors import KNeighborsClassifier
from sklearn.utils.validation import check_is_fitted

from mibici import config as cfg


class SeasonalDemand(RegressorMixin, BaseEstimator):
    def fit(self, X, y):
        self.feature_names_in_ = np.asarray(X.columns, dtype=object)
        self.n_features_in_ = len(X.columns)
        keys = ["station_id", "weekday", "hour"]
        frame = X[keys].copy()
        frame["target"] = np.asarray(y, dtype=float)
        means = frame.groupby(keys)["target"].mean()
        self.mean_keys_ = means.index.to_frame(index=False).to_numpy()
        self.mean_values_ = means.to_numpy()
        self.global_mean_ = float(np.mean(y))
        return self

    def predict(self, X):
        check_is_fitted(self, "mean_values_")
        lag = X["departures_lag_168"].astype(float)
        if not lag.isna().any():
            return lag.to_numpy()
        keys = ["station_id", "weekday", "hour"]
        means = pd.DataFrame(self.mean_keys_, columns=keys)
        means["fallback"] = self.mean_values_
        fallback = X[keys].join(means.set_index(keys)["fallback"], on=keys)["fallback"]
        return lag.fillna(fallback).fillna(self.global_mean_).to_numpy()


class PersistenceRisk(ClassifierMixin, BaseEstimator):
    def __init__(self, low=cfg.LOW_OCCUPANCY, high=cfg.HIGH_OCCUPANCY):
        self.low = low
        self.high = high

    def fit(self, X, y=None):
        self.classes_ = np.array([0, 1, 2], dtype="int8")
        self.feature_names_in_ = np.asarray(X.columns, dtype=object)
        self.n_features_in_ = len(X.columns)
        return self

    def predict(self, X):
        check_is_fitted(self, "classes_")
        values = X["virtual_occupancy"].to_numpy(dtype=float)
        return np.select([values <= self.low, values >= self.high], [1, 2], default=0).astype(
            "int8"
        )

    def predict_proba(self, X):
        return (self.predict(X)[:, None] == self.classes_[None, :]).astype(float)


class StationGroups(ClusterMixin, BaseEstimator):
    def __init__(
        self,
        algorithm="kmeans",
        n_clusters=cfg.N_CLUSTERS,
        random_state=cfg.SEED,
        n_init=cfg.KMEANS_N_INIT,
    ):
        self.algorithm = algorithm
        self.n_clusters = n_clusters
        self.random_state = random_state
        self.n_init = n_init

    def fit(self, X, y=None):
        self.feature_names_in_ = np.asarray(X.columns, dtype=object)
        self.n_features_in_ = len(X.columns)
        if self.algorithm == "kmeans":
            self.estimator_ = KMeans(
                n_clusters=self.n_clusters, n_init=self.n_init, random_state=self.random_state
            )
        elif self.algorithm == "ward":
            self.estimator_ = AgglomerativeClustering(n_clusters=self.n_clusters, linkage="ward")
        else:
            raise ValueError(f"Algoritmo desconocido: {self.algorithm}")
        values = X.to_numpy(dtype=float)
        self.labels_ = self.estimator_.fit_predict(values)
        self.assignment_rule_ = (
            "nearest_centroid" if self.algorithm == "kmeans" else "nearest_training_profile"
        )
        if self.algorithm == "ward":
            self.assignment_ = KNeighborsClassifier(n_neighbors=1, algorithm="brute").fit(
                values, self.labels_
            )
        return self

    def predict(self, X):
        check_is_fitted(self, "estimator_")
        values = X[list(self.feature_names_in_)].to_numpy(dtype=float)
        if self.algorithm == "kmeans":
            return self.estimator_.predict(values)
        return self.assignment_.predict(values)
