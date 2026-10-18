# Protocolo del experimento base | Equipo 45

Las seis configuraciones y la semilla 42 quedan fijadas en Git antes de ejecutar el experimento. No se buscan hiperparámetros ni se modifica un modelo después de observar septiembre.

- Entrenamiento: enero-junio, excluyendo la historia inicial insuficiente.
- Validación: julio-agosto; se comparan las configuraciones propuestas.
- Prueba final: septiembre; se evalúa una vez por configuración de P1/P2 mediante `--final-test`, después de fijar este protocolo.
- P3 compara perfiles de entrenamiento y validación mediante ARI entre estaciones comunes. La versión actual no calcula métricas de prueba para P3; no se atribuyen resultados de septiembre a esta pregunta.
- P1: estacional semanal y `HistGradientBoostingRegressor(loss="poisson")`.
- P2: regresión logística balanceada con escalado aprendido en entrenamiento y `HistGradientBoostingClassifier(class_weight="balanced")`.
- P3: K-means y Ward, ambos con tres grupos. Las coordenadas se reservan para el mapa.

La prueba no se usa para cambiar estos modelos. El valor inicial de ocupación virtual utilizado en esta entrega es 0.5.

Cada run registra commit real, versiones de datos y variables, fechas, semilla, hiperparámetros del estimador, métricas por conjunto y artefactos. Las figuras son agregadas y no muestran personas usuarias.

Las funciones de `features.py` incluyen docstrings sobre su operación y su pertinencia para P1-P3. La documentación Markdown amplía los supuestos y las decisiones del proyecto.

## Comandos

```bash
python -m mibici.dataset --verify
python -m mibici.features --verify
python -m unittest discover -s tests -v
python -m mibici.train --question all --final-test
python -m mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5000
```

La ejecución requiere primero la ingesta y las variables del README. El notebook es exploratorio y se puede ejecutar con Jupyter. No contiene entrenamiento ni comentarios en las celdas de código.
