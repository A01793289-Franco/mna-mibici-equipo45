# Pruebas y CI

## Comprobación local

Con las dependencias instaladas:

```text
python -m flake8 mibici
python -m unittest discover -s tests -v
python -m mkdocs build --strict -f docs/mkdocs.yml
```

La suite usa datos sintéticos y almacenes temporales de MLflow. No descarga viajes ni requiere un servidor de tracking externo. Las pruebas de la API usan `TestClient` y comprueban predicciones, fechas, datos ausentes y errores de entrada.

Para verificar los datos reales y modelos generados en tu máquina:

```text
python -m mibici.dataset --verify
python -m mibici.features --verify
python -m mibici.verify_registry --question all
```

## GitHub Actions

El archivo `.github/workflows/ci.yml` se ejecuta en cada Pull Request y en los pushes de `main` y de la rama de integración. También permite una ejecución manual. La matriz usa Ubuntu y Windows con Python 3.13.15.

Cada trabajo instala las dependencias, ejecuta lint, corre las pruebas y construye MkDocs en modo estricto. Si falla un comando, el trabajo queda en rojo. No se ignoran errores y no se descargan datos reales ni se guardan modelos de producción en el repositorio.

El token del trabajo solo tiene permiso de lectura del contenido. Las acciones de checkout y preparación de Python están fijadas a commits de sus repositorios oficiales.

[Consultar las ejecuciones de CI](https://github.com/A01793289-Franco/mna-mibici-equipo45/actions/workflows/ci.yml).

Las verificaciones automáticas complementan la revisión del PR. La fusión y la participación de los integrantes se comprueban en el historial de GitHub.
