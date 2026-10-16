# MiBici | Equipo 45

Propuesta de Machine Learning para apoyar la operación de MiBici en Guadalajara.

| Pregunta | Definición acordada |
|---|---|
| P1: demanda | Viajes iniciados por estación durante la siguiente hora. |
| P2: riesgo | Riesgo virtual de falta de bicicletas o anclajes al cierre de la siguiente hora. |
| P3: patrones | Tres grupos iniciales por perfil horario de uso, ubicados en un mapa. |

## Estado actual

Existen la estructura inicial de Cookiecutter Data Science, la configuración centralizada y la propuesta detallada. Ingesta, variables, entrenamiento y runs reales de MLflow siguen pendientes. Los documentos describen el diseño, no resultados ejecutados.

- [ML Canvas editable](references/ml_canvas.md).
- [ML Canvas en PDF](references/Machine%20Learning%20Canvas.pdf).
- [Propuesta: datos, partición, pipelines, modelos y métricas](references/propuesta.md).
- [Arquitectura y justificación](references/arquitectura.md).
- [Diagrama editable](references/arquitectura.svg).

## Datos y configuración

Fuente: [datos abiertos de MiBici](https://www.mibici.net/es/datos-abiertos/). Se proponen nueve meses completos, enero-septiembre de 2026, y el catálogo de septiembre.

Entrenamiento: enero-junio; validación: julio-agosto; prueba: septiembre. Los intervalos incluyen inicio y excluyen fin. Las variables de cada hora solo podrán usar eventos anteriores al momento de predecir.

El tamaño real de viajes, estaciones y descartes deberá obtenerse con la ingesta. Todavía no se han descargado ni medido esos datos aquí. La propuesta explica las limitaciones del catálogo posterior y del riesgo simulado de P2.

`mibici/config.py` centraliza rutas, fuentes, fechas, semilla, horizontes, umbrales y parámetros de clustering. Los próximos módulos deberán importar esos valores.

## Estructura actual

```text
mibici/
  __init__.py
  config.py
references/
  Machine Learning Canvas.pdf
  ml_canvas.md
  propuesta.md
  arquitectura.md
  arquitectura.svg
notebooks/
models/
reports/figures/
docs/
requirements.txt
pyproject.toml
```

`python -m mibici.config` crea `data/raw`, `data/interim` y `data/processed` localmente, sin versionar datos. `notebooks` se reserva para exploración; `models` para salidas locales y `reports/figures` para evidencia sin datos personales.

## Instalación

Se conserva Python 3.13 de la plantilla. Desde la raíz:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m mibici.config
```

En PowerShell se activa con `.venv\Scripts\Activate.ps1`. Las dependencias directas tienen versiones fijas. Estos comandos preparan el entorno y las carpetas; aún no hay comando implementado de ingesta ni entrenamiento.

## Flujo de trabajo propuesto

- Ramas `feat/descripcion`, `fix/descripcion`, `docs/descripcion` o `chore/descripcion`.
- Commits `tipo: descripción`, por ejemplo `feat: agrega ingesta mensual`.
- Cada cambio entra mediante Pull Request revisado por otro integrante.
- Proteger `main` y exigir revisión: configuración pendiente del administrador.
- Cada uno de los cuatro integrantes debe abrir y revisar al menos un PR. Nombres y roles quedan pendientes de confirmación del equipo.

## Reproducibilidad y privacidad

Se propone un manifiesto con URL, SHA-256 y conteos, versionado sin los archivos de datos. Cada run deberá registrar esa versión, commit, pregunta, fechas, semilla, modelo, parámetros, métricas con prefijo del conjunto y al menos un artefacto.

`.gitignore` excluye datos, modelos serializados, `mlruns`, `mlartifacts`, la base local de MLflow y archivos de entorno. MIT cubre el código; las condiciones de uso de los datos deberán documentarse como indica la propuesta.

## Pendientes de la entrega completa

1. Implementar `dataset.py`, manifiesto y cifras reales.
2. Implementar `features.py`, entrenamiento y evaluación de P1-P3.
3. Crear el notebook exploratorio y ejecutar los baselines en MLflow.
4. Capturar lista, detalle, artefacto y comparación de runs.
5. Completar participación de cuatro integrantes, revisiones y protección de `main`.
6. Integrar el PDF final y ajustar el nombre del repositorio al formato solicitado.

Referencias bibliográficas y justificaciones: [propuesta](references/propuesta.md).
