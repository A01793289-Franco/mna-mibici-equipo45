# Operación de MiBici con Compose y CI/CD

## Arquitectura y alcance

`docker-compose.yml` coordina tres servicios de la misma imagen, construida con el
`Containerfile` existente y `requirements-api.txt`:

| Servicio | Responsabilidad | Dependencia |
|---|---|---|
| `mlflow` | Tracking, Model Registry y entrega HTTP de artefactos | Volumen persistente `registry` |
| `registry-init` | Importa P1/P2 desde el paquete exportado y reproduce sus predicciones | MLflow saludable; termina con código 0 |
| `api` | FastAPI, predicción síncrona P1/P2 y documentación OpenAPI | MLflow saludable e importación completada |

El despliegue reutiliza modelos ya registrados. No vuelve a entrenar ni cambia los alias
del Registry de origen. Cada importación conserva nombre, versión de origen, run, etiquetas
de código/datos disponibles, firma, ejemplo y prueba de reproducción. En el Registry de
servicio se crean versiones propias; sus números pueden diferir del origen. El alias
`champion` se asigna después de comprobar ambos modelos. Los mismos paquetes se reutilizan
al reiniciar sin crear versiones duplicadas. Un champion de otro paquete detiene la
importación para evitar una sustitución silenciosa.

El paquete elimina del archivo `MLmodel` únicamente el identificador de modelo ligado a
la base de origen; conserva su procedencia en `bundle.json`. Los estimadores permanecen
intactos. Se verifican hashes SHA-256, firma, predicciones y probabilidades con tolerancia
`1e-12`. Los hashes detectan cambios accidentales; utiliza exclusivamente modelos de un
Registry confiable. No son una firma de autenticidad.

## Requisitos y preparación del modelo

Se requiere Docker Engine/Desktop en ejecución y Docker Compose v2.20 o posterior, con
contenedores Linux. Los comandos `docker compose` son iguales en Linux, macOS y Windows.
En Windows, usa Docker Desktop con backend Linux. Esta entrega elige Docker Compose;
no se declara una validación de `podman-compose`.

Desde la raíz del repositorio, instala el entorno del proyecto y apunta al Registry que
ya contiene `mibici-p1-demanda@champion` y `mibici-p2-riesgo@champion`. No copies una base
SQLite con rutas absolutas a la imagen. Si el Registry es remoto, sus artefactos también
deben ser accesibles mediante HTTP.

```text
python -m pip install --only-binary=:all: -r requirements.txt
```

Define el origen según tu terminal (el ejemplo usa el puerto 5001):

| Terminal | Comando |
|---|---|
| Linux/macOS, bash | `export MLFLOW_TRACKING_URI=http://127.0.0.1:5001` |
| Windows, PowerShell | `$env:MLFLOW_TRACKING_URI = "http://127.0.0.1:5001"` |
| Windows, CMD | `set MLFLOW_TRACKING_URI=http://127.0.0.1:5001` |

Si todavía no tienes los modelos registrados, utiliza primero la
[guía del MLflow Project](mlflow_project.md) para levantar el Registry, ejecutar la ingesta,
construir variables y entrenar. La ingesta descubre el catálogo publicado cuando la URL
histórica fue retirada; registra su nueva versión en vez de exigir editar código.

Exporta una sola vez los dos modelos desde ese Registry:

```text
python -m mibici.registry_bundle export --directory models/serving
```

`models/serving` queda excluido de Git. Se necesita esta preparación porque los modelos
serializados y las bases de MLflow no se versionan en el repositorio. La exportación falla
si el destino ya existe; para preparar una versión distinta, utiliza otro directorio.
Se puede detener el servidor de origen después de exportar: el servicio conservará su
propia copia de los artefactos. Si el servidor de origen ocupa el puerto 5000, cambia
`MLFLOW_PORT` en `.env` o detenlo antes del arranque.

## Levantar y comprobar con un solo comando

```text
docker compose up --build -d --wait --wait-timeout 240
```

La red `serving` resuelve MLflow como `http://mlflow:5000`; esta dirección se establece
explícitamente dentro de la API. La variable del Registry de origen de la terminal no
reemplaza la dirección interna. La base SQLite y los artefactos HTTP se conservan juntos
en un volumen de Docker, sin depender de rutas del anfitrión. El paquete se monta de solo
lectura. Los servicios corren como UID 1000, sin capacidades adicionales, con raíz de solo
lectura, directorio temporal y límites de CPU/memoria. La imagen inicializa el propietario
del volumen vacío. Los puertos se publican únicamente en `127.0.0.1`.

```text
docker compose ps --all
python -m mibici.verify_api --output reports/compose/http-local.json
```

El verificador comprueba 11 condiciones HTTP: estado, contratos OpenAPI, dos predicciones
válidas y siete entradas inválidas que deben devolver 422. Abre
`http://127.0.0.1:8000/docs` para hacer peticiones y `http://127.0.0.1:5000` para el Registry.
`/health` confirma el proceso; no sustituye la verificación de inferencia contra el Registry.

Ejemplo de cuerpo para `POST /predict/p1`, utilizable desde Swagger:

```json
{
  "station_id": 2,
  "hour": 8,
  "weekday": 5,
  "is_weekend": 1,
  "month": 8,
  "departures_lag_1": 2.0,
  "departures_lag_24": 3.0,
  "departures_lag_168": 4.0,
  "departures_mean_24": 2.5,
  "departures_mean_168": 3.5
}
```

La respuesta contiene `question`, `model_uri` y `prediction.demanda_esperada`. El valor
numérico depende de la versión exportada. P2 sigue representando riesgo de inventario
virtual; sus salidas no equivalen a disponibilidad real ni a probabilidades calibradas.

### Configuración opcional

Copia `.env.example` a `.env` y define solo las opciones que quieras cambiar:

| Variable | Valor predeterminado | Uso |
|---|---|---|
| `API_PORT` | `8000` | Puerto del anfitrión para FastAPI |
| `MLFLOW_PORT` | `5000` | Puerto del anfitrión para Tracking/UI |
| `MIBICI_MODEL_BUNDLE` | `./models/serving` | Directorio exportado, ya existente |
| `MIBICI_IMAGE` | `mibici-api:local` | Etiqueta local de la imagen |

Los límites iniciales son 2 CPU/1 GiB para API, 1 CPU/1 GiB para MLflow y 1 CPU/1 GiB
para la importación temporal. Son parámetros de partida; no constituyen mediciones de
capacidad ni un análisis FinOps. `docker compose stats` permite observar el consumo.

### Parar, recrear y diagnosticar

```text
docker compose logs --tail 100 mlflow registry-init api
docker compose down
docker compose up -d --wait --wait-timeout 240
python -m mibici.verify_api --output reports/compose/http-restart.json
```

`down` conserva el volumen. `down --volumes` elimina exclusivamente el Registry de este
proyecto Compose, incluidas sus versiones; úsalo solo si quieres reconstruirlo desde el
paquete. No afecta al Registry de origen. El nombre del proyecto se puede cambiar con
`docker compose -p nombre ...` para aislar otra instancia; asigna también puertos distintos.

Si falta el directorio de modelos, exporta el paquete. Si la importación termina con error,
consulta los logs antes de intentar arrancar la API. Si falta un alias o un artefacto, no
lo sustituyas por un modelo sintético. Si un puerto está ocupado, cambia `.env`.

## Pipeline automático

`.github/workflows/ci.yml` se ejecuta en cada `push`, `pull_request` y ejecución manual.
Conserva los controles anteriores y añade el job `compose`, que depende de las pruebas
en Ubuntu/Windows y de seguridad:

1. Instala las versiones declaradas con caché de pip.
2. Crea un Registry temporal con dos baselines de datos sintéticos y exporta un paquete
   mediante el mismo mecanismo que se usa con modelos reales.
3. Construye el `Containerfile` con Buildx y caché de capas de GitHub Actions.
4. Valida el YAML y despliega MLflow/API en el runner con Compose y espera sus estados.
5. Verifica las 11 condiciones HTTP de P1/P2.
6. Recrea todos los contenedores conservando el volumen y repite las peticiones; la
   importación debe ser idempotente.
7. Guarda JSON de verificaciones, estado de servicios y logs como artefacto de Actions
   durante 14 días, incluso si falla un paso. Libera después contenedores y volumen.

Es un despliegue de prueba efímero en el runner; no publica una API permanente en la nube.
Los modelos de `tests/compose_seed.py` llevan la etiqueta `synthetic_ci_only` y solo
comprueban la integración del sistema. No aportan métricas de calidad del proyecto ni
sustituyen la validación local con los modelos reales. Las acciones externas están
fijadas a commits y el workflow utiliza permisos de lectura del repositorio.

Para reproducir exclusivamente esa comprobación de integración, exporta los ejemplos
sintéticos a una carpeta separada y selecciona esa carpeta en `.env`:

```text
python -m tests.compose_seed --directory models/ci-serving
```

Utiliza un proyecto Compose y puertos distintos de los reales, y comprueba siempre la
etiqueta del paquete. La suite unitaria completa conserva un único comando:

```text
python -m pytest -v
```

## Referencias técnicas

- Docker. [Control startup and shutdown order in Compose](https://docs.docker.com/compose/how-tos/startup-order/).
- Docker. [Networking in Compose](https://docs.docker.com/compose/how-tos/networking/).
- MLflow. [MLflow Tracking Server](https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/).
- GitHub. [Publishing Docker images](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images).
