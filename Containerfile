FROM docker.io/library/python:3.13.15-slim
WORKDIR /app
COPY requirements-api.txt .
RUN pip install --no-cache-dir --only-binary=:all: -r requirements-api.txt
COPY mibici ./mibici
# Falla pronto si MLflow no responde, en lugar de reintentar durante minutos.
ENV MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib \
    MLFLOW_HTTP_REQUEST_MAX_RETRIES=2 \
    MLFLOW_HTTP_REQUEST_TIMEOUT=10
USER 1000
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "mibici.api:app", "--host", "0.0.0.0", "--port", "8000"]
