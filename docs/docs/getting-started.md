# Reproducir el proyecto

## Preparación

Clona el repositorio y entra en su carpeta:

```text
git clone https://github.com/A01793289-Franco/mna-mibici-equipo45.git
cd mna-mibici-equipo45
```

Se utiliza Python 3.13. La especificación automática de MLflow fija 3.13.15.

Linux o macOS:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
```

PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

CMD:

```text
py -3.13 -m venv .venv
.venv\Scripts\activate.bat
```

En cualquier sistema, instala las versiones de las dependencias:

```text
python -m pip install -r requirements.txt
```

## MLflow

En una terminal, desde la raíz, inicia el servidor:

```text
python -m mlflow server --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1 --port 5000
```

En otra terminal, con el entorno activado, define la conexión:

| Sistema | Comando |
|---|---|
| Linux / macOS | `export MLFLOW_TRACKING_URI=http://127.0.0.1:5000` |
| PowerShell | `$env:MLFLOW_TRACKING_URI="http://127.0.0.1:5000"` |
| CMD | `set MLFLOW_TRACKING_URI=http://127.0.0.1:5000` |

Después ejecuta:

```text
python -m mlflow run . -e ingest --env-manager local --experiment-name mibici-equipo45
python -m mlflow run . -e train --env-manager local --experiment-name mibici-equipo45 -P question=all -P tune=true
python -m mlflow run . -e verify --env-manager local --experiment-name mibici-equipo45
```

`ingest` descarga los archivos, los normaliza y construye las variables. `train` registra las corridas y los modelos elegidos. `verify` carga los tres aliases `champion` y reproduce las métricas de validación.

`local` reutiliza el entorno activo. Con uv instalado, `--env-manager uv` permite que MLflow cree el entorno de `python_env.yaml`.

La [guía completa](https://github.com/A01793289-Franco/mna-mibici-equipo45/blob/main/references/mlflow_project.md) describe los parámetros por modelo. El conjunto de prueba no participa en la selección automática.

## Predicción

La [API](api.md) permite consultar una estación y hora de P1/P2. Los comandos de consola también se conservan:

```text
python -m mibici.predict --question P1 --timestamp 2026-08-15T08:00
python -m mibici.predict --question P2 --timestamp 2026-08-15T08:00
python -m mibici.predict --question P3 --split val
```

Los datos, modelos serializados y archivos de MLflow se generan localmente y se excluyen de Git. La ingesta completa necesita espacio y memoria para procesar millones de viajes.

## Atajos con Make

Con `make` disponible, `make data`, `make features`, `make verify` y `make test` ejecutan los módulos individuales y sus comprobaciones. `make train` conserva el entrenamiento directo del módulo, solo con validación. Para registrar las corridas de esta entrega se utilizan las entradas de `mlflow run` indicadas arriba, que conservan el padre del Project y su entorno declarado.
