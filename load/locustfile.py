"""Escenario de carga de Locust para la API de MiBici (``/predict/p1`` y ``/predict/p2``).

Cada usuario virtual envía variables válidas y aleatorias a P1 y P2, consulta ``/health`` y,
de vez en cuando, una petición inválida que debe responder 422. Una respuesta cuenta como
éxito solo si el código HTTP y el cuerpo son los esperados; así la tasa de error mide fallos
reales del servicio y no solo caídas de conexión.

Se ejecuta con ``python -m mibici.load_test`` (ver README) o directamente con Locust::

    locust -f load/locustfile.py --host http://127.0.0.1:8000
"""

import os
import random

from locust import HttpUser, between, task

# Las estaciones desconocidas para el modelo caen en el grupo "otras", así que cualquier
# identificador válido sirve para la prueba.
STATION_IDS = int(os.getenv("LOCUST_STATION_IDS", "400"))
WAIT_MIN = float(os.getenv("LOCUST_WAIT_MIN", "0.1"))
WAIT_MAX = float(os.getenv("LOCUST_WAIT_MAX", "0.5"))


def p1_variables():
    weekday = random.randint(0, 6)
    return {
        "station_id": random.randint(1, STATION_IDS),
        "hour": random.randint(0, 23),
        "weekday": weekday,
        "is_weekend": int(weekday >= 5),
        "month": random.randint(1, 12),
        "departures_lag_1": round(random.uniform(0, 15), 1),
        "departures_lag_24": round(random.uniform(0, 15), 1),
        "departures_lag_168": round(random.uniform(0, 15), 1),
        "departures_mean_24": round(random.uniform(0, 12), 2),
        "departures_mean_168": round(random.uniform(0, 12), 2),
    }


def p2_variables():
    return {
        **p1_variables(),
        "virtual_occupancy": round(random.uniform(0, 1), 3),
        "net_flow_lag_1": round(random.uniform(-8, 8), 1),
        "net_flow_lag_24": round(random.uniform(-8, 8), 1),
    }


class MiBiciUser(HttpUser):
    wait_time = between(WAIT_MIN, WAIT_MAX)

    def predict(self, question, payload):
        path = f"/predict/{question.lower()}"
        with self.client.post(path, json=payload, name=path, catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
                return
            try:
                body = response.json()
            except ValueError:
                response.failure("la respuesta no es JSON")
                return
            if body.get("question") != question or "prediction" not in body:
                response.failure("cuerpo inesperado")
            else:
                response.success()

    @task(5)
    def predict_p1(self):
        self.predict("P1", p1_variables())

    @task(3)
    def predict_p2(self):
        self.predict("P2", p2_variables())

    @task(1)
    def health(self):
        self.client.get("/health", name="/health")

    @task(1)
    def invalid_request(self):
        """Una entrada fuera de rango debe rechazarse con 422, no provocar un error 500."""
        name = "/predict/p1 [invalida]"
        payload = {**p1_variables(), "hour": 24}
        with self.client.post("/predict/p1", json=payload, name=name, catch_response=True) as r:
            if r.status_code == 422:
                r.success()
            else:
                r.failure(f"se esperaba HTTP 422; recibido {r.status_code}")
