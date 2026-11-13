# Pruebas del proyecto

Desde la raíz, instala `requirements-validation.txt` en el entorno del proyecto. Toda la suite se ejecuta con un comando, igual en Linux, macOS y Windows:

```text
python -m pytest -v
```

`pyproject.toml` fija `tests/` como carpeta de descubrimiento. PyTest ejecuta las pruebas existentes de `unittest` y las nuevas basadas en fixtures. `conftest.py` contiene las tablas sintéticas y el almacén temporal de MLflow.

| Grupo | Archivos |
|---|---|
| Ingesta y variables | `test_data_features.py`, `test_dataset_utils.py`, `test_hourly_counts.py` |
| Entrenamiento y reproducibilidad | `test_train.py`, `test_stations.py`, `test_sensitivity.py`, `test_reproducibility.py` |
| MLflow Project y Registry | `test_project.py`, `test_registry_integration.py`, `test_predict.py` |
| Validación DeepChecks y monitoreo Evidently | `test_validation.py`, `test_monitoring.py` |
| API y seguridad | `test_api.py`, `test_security.py`, `test_repository_security.py` |
| Recuperación y variables de la API | `test_model_loader.py`, `test_api_variables.py` |
| Verificador HTTP y salidas del modelo | `test_verify_api.py` |

Para ejecutar únicamente los controles de seguridad y privacidad:

```text
python -m pytest tests/test_security.py tests/test_repository_security.py -v
```

Los repositorios Git, archivos de datos y modelos que necesitan las pruebas se crean en carpetas temporales. La suite usa ejemplos sintéticos y no requiere el dataset real ni el servidor de MLflow del equipo.

El escaneo del repositorio y su historial es una comprobación adicional, separada de los ejemplos sintéticos:

```text
python -m mibici.security --history --output reports/security/repositorio.json
python -m bandit -c pyproject.toml -r mibici -ll
```

La [guía de verificación](../docs/docs/verificacion.md) explica DeepChecks, la auditoría de dependencias y sus excepciones documentadas.

La verificación contra un contenedor y un Registry reales se ejecuta por separado: `python -m mibici.verify_api --base-url http://127.0.0.1:8000`. No forma parte de las pruebas unitarias de CI; requiere iniciar el servicio con sus modelos. Su [evidencia](../reports/deployment/README.md) incluye los controles de ausencia de Registry y las versiones recuperadas.
