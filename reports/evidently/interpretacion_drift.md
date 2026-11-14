# Interpretación de resultados de Data Drift — MiBici

**Entregable 8 — Punto 3: Interpretación de resultados**  
**Proyecto:** MiBici — Equipo 45  
**Herramienta:** Evidently 0.7.23

## 1. Objetivo

Interpretar los cambios detectados entre los datos de entrenamiento y los datos de periodos posteriores, identificar las variables que presentan *data drift* y analizar sus posibles implicaciones para el desempeño de los modelos P1 y P2.

El análisis se basa en los resultados generados por Evidently y documentados en `reports/evidently/resumen.md`.

## 2. Periodos y metodología

| Conjunto | Periodo | Propósito |
|---|---|---|
| Referencia | 8 de enero al 30 de junio de 2026 | Entrenamiento |
| Periodo intermedio | Julio–agosto de 2026 | Validación temporal |
| Periodo actual | Septiembre de 2026 | Simulación de producción |

Se utilizaron dos métodos de comparación:

- **Distancia de Wasserstein normalizada:** para variables numéricas.
- **Distancia Jensen-Shannon:** para variables categóricas.

El umbral configurado es de **0.10**. Una variable presenta drift cuando su distancia alcanza o supera este valor.

El conjunto completo se considera con drift cuando al menos el 50 % de las variables evaluadas presenta drift.

La referencia empieza el 8 de enero y no el 1 porque las primeras 168 horas no tienen historia para los rezagos y medias de siete días y se excluyen al construir las variables. `station_id`, `hour`, `weekday` e `is_weekend` se tratan como categóricas: son códigos o valores discretos sin una distancia numérica con sentido (la estación 300 no está "más lejos" de la 2 que la 3), por eso se comparan con Jensen-Shannon. `month` se excluye porque cada periodo cubre meses distintos y siempre mostraría drift. P3 queda fuera: agrupa estaciones por lotes, no hace predicciones por hora y no forma parte de la API.

## 3. Resultados generales

| Modelo | Periodo | Variables con drift | Drift global |
|---|---|---|---|
| P1 | Julio–agosto | 2 de 9 (22.2 %) | No |
| P1 | Septiembre | 1 de 9 (11.1 %) | No |
| P2 | Julio–agosto | 2 de 12 (16.7 %) | No |
| P2 | Septiembre | 1 de 12 (8.3 %) | No |

**Interpretación:** ninguno de los conjuntos presenta drift global según el criterio establecido. Sin embargo, se identificaron cambios individuales relevantes que requieren seguimiento.

La ausencia de drift global no significa que todas las variables permanezcan estables ni garantiza que el desempeño predictivo sea el mismo.

## 4. Análisis de las variables con drift

### 4.1. Variable `station_id`

La variable `station_id` presentó drift en ambos modelos y en los dos periodos posteriores.

| Modelo | Julio–agosto | Septiembre | Umbral |
|---|---|---|---|
| P1 | 0.2285 | 0.2620 | 0.10 |
| P2 | 0.2266 | 0.2605 | 0.10 |

En septiembre, el conjunto P1 contiene 471 estaciones, frente a 413 del entrenamiento. Se identificaron **58 estaciones ausentes de la referencia**, que representan aproximadamente el 12.2 % de los registros actuales.

En P2 también se identificaron 58 estaciones nuevas, correspondientes aproximadamente al 12.3 % de los registros actuales.

**Interpretación técnica**

El cambio indica una modificación en la composición de estaciones o en su frecuencia relativa dentro del conjunto de datos.

La incorporación de estaciones no observadas durante el entrenamiento podría representar un riesgo para la capacidad de generalización de los modelos, especialmente si estas estaciones presentan patrones de demanda o disponibilidad diferentes.

No obstante, el drift de `station_id` no demuestra por sí mismo una pérdida de precisión.

**Implicaciones potenciales**

- **P1:** el champion (HGB con estación) asigna las estaciones no vistas a la categoría "otras" (`mibici/stations.py`). Para el 12.2 % de las filas de septiembre predice sin un efecto propio de la estación, solo con calendario y demanda reciente. Ahí se espera el mayor error relativo, aunque las métricas disponibles son globales y no permiten confirmarlo (sección 6).
- **P2:** el champion es la regla de persistencia, que solo usa `virtual_occupancy` (`mibici/deployable.py`). El drift de `station_id` no la afecta directamente; el riesgo aplicaría si el champion pasara a ser un modelo que use la estación.
- Las métricas globales podrían ocultar problemas concentrados en determinadas estaciones.

**Recomendación:** evaluar el desempeño por estación, diferenciando entre estaciones conocidas y nuevas.

### 4.2. Variable `departures_mean_168`

La variable `departures_mean_168` presentó drift durante julio–agosto, pero no durante septiembre.

| Modelo | Distancia julio–agosto | Umbral | Media referencia | Media actual |
|---|---|---|---|---|
| P1 | 0.1052 | 0.10 | 1.297 | 1.173 |
| P2 | 0.1030 | 0.10 | 1.298 | 1.177 |

Esta variable representa el promedio móvil de salidas durante una ventana de 168 horas, equivalente a siete días.

**Interpretación técnica**

La disminución de la media indica un cambio en el comportamiento histórico de las salidas durante julio–agosto.

El cambio podría estar relacionado con factores estacionales, vacaciones o modificaciones operativas. Sin embargo, estas posibles causas no han sido verificadas y requieren investigación adicional.

**Implicaciones potenciales**

- Cambios en los patrones de demanda utilizados por P1.
- Modificaciones indirectas en las condiciones de entrada utilizadas por P2.
- Posibles diferencias de desempeño entre temporadas.

**Recomendación:** monitorear la variable por semana, estación y temporada, y contrastar sus cambios con las métricas predictivas.

### 4.3. Variables cercanas al umbral

En septiembre, `departures_mean_24` registró las siguientes distancias:

| Modelo | Distancia | Umbral | Drift |
|---|---|---|---|
| P1 | 0.0953 | 0.10 | No |
| P2 | 0.0974 | 0.10 | No |

Aunque no se detectó drift en esta variable, sus resultados se encuentran próximos al umbral.

Se recomienda mantenerla bajo observación para identificar posibles cambios posteriores.

## 5. Calidad de los datos

El resumen de datos de Evidently y las comprobaciones propias de `mibici/monitoring.py` (duplicados por estación y hora, estaciones nuevas) indican:

- Cero valores faltantes.
- Cero filas duplicadas por estación y hora.
- Ninguna columna constante.

Estos resultados sugieren consistencia estructural en los conjuntos analizados.

Sin embargo, una buena calidad estructural no garantiza que los datos sean representativos de todas las condiciones de operación ni que las predicciones mantengan su desempeño.

## 6. Desempeño observado en los periodos posteriores

Las métricas ya se calcularon en la segunda entrega (`reports/resultados_mlflow_entrega2.md`): julio–agosto como validación y septiembre como evaluación retrospectiva. Se citan aquí sin volver a evaluar ningún modelo, así que no se usa de nuevo el conjunto de prueba.

### Modelo P1 — Predicción de demanda (champion: HGB con estación)

| Periodo | Demanda media por estación-hora | MAE | WAPE |
|---|---|---|---|
| Julio–agosto | 1.17 | 0.750 | 64.0 % |
| Septiembre | 1.44 | 0.862 | 59.7 % |

La demanda media se obtiene como MAE ÷ WAPE y coincide con la media de `departures_lag_1` del resumen de Evidently. En septiembre el MAE sube 15 % mientras la demanda sube 23 %; el WAPE, que divide el error entre la demanda, baja. El error crece en viajes porque hay más viajes, no porque el modelo empeore en términos relativos. La referencia estacional, que no aprende nada, sube en la misma proporción (MAE de 0.899 a 1.026, +14 %), lo que confirma que el cambio viene del nivel de demanda del periodo. Coincide con Evidently: las variables de demanda reciente se mueven en el sentido del nivel (bajan en julio–agosto, suben en septiembre) sin superar el umbral en septiembre.

### Modelo P2 — Clasificación de riesgo (champion: persistencia)

El F1 macro pasa de 0.882 en julio–agosto a 0.870 en septiembre (−1.5 %). La regla solo usa `virtual_occupancy`, que no presenta drift en ningún periodo (0.075 en septiembre, 0.047 en julio–agosto), y su desempeño se mantiene.

**Límite:** las métricas son globales. No hay desglose entre estaciones conocidas y nuevas, que es donde el drift de `station_id` podría concentrar el error de P1.

**Importante:** Evidently identificó cambios en las distribuciones de las variables de entrada; las métricas de esta sección son las que permiten afirmar que, por ahora, esos cambios no se traducen en deterioro relativo.

## 7. Recomendaciones técnicas

1. Mantener el monitoreo periódico de `station_id`, `departures_mean_168` y `departures_mean_24`.
2. En la próxima evaluación, desglosar el error de P1 entre estaciones conocidas y nuevas; las métricas actuales son globales.
3. Comparar resultados entre estaciones conocidas y estaciones nuevas.
4. Investigar los cambios en el catálogo y la participación relativa de las estaciones.
5. Complementar las alertas globales con monitoreo por variable y segmento.
6. No reentrenar solo por drift. El motivo concreto son las estaciones nuevas: cuando acumulen historia, un reentrenamiento les daría categoría propia en P1. La nueva versión se registra en MLflow y sustituye al champion solo si mejora la validación.
7. Evitar utilizar repetidamente el conjunto reservado para prueba final durante la selección de modelos o hiperparámetros.

## 8. Conclusión

Los resultados obtenidos mediante Evidently indican que los modelos P1 y P2 no presentan drift global bajo el criterio configurado.

Sin embargo, se identificaron dos hallazgos relevantes:

**Primero**, la variable `station_id` presenta un cambio persistente en los periodos posteriores, asociado con diferencias en la distribución de estaciones y la presencia de 58 estaciones no observadas durante el entrenamiento.

**Segundo**, `departures_mean_168` presenta un cambio temporal durante julio–agosto, lo que sugiere modificaciones en los patrones históricos de demanda.

Las métricas ya calculadas muestran que estos cambios no deterioran el desempeño relativo: el MAE de P1 sube con la demanda pero su WAPE baja, y el F1 macro de P2 apenas cambia. Estos hallazgos justifican mantener un monitoreo continuo y evaluar el desempeño por periodo y estación.

**No se recomienda reemplazar inmediatamente los modelos únicamente por los resultados de drift.** La decisión de reentrenamiento debe complementarse con la comparación de métricas de desempeño y la evaluación de versiones alternativas registradas en MLflow.

## 9. Evidencia y trazabilidad

Los resultados analizados provienen de los siguientes archivos del repositorio:

- `reports/evidently/resumen.md`
- `reports/evidently/resumen.json`
- `reports/evidently/p1_sep.html`
- `reports/evidently/p2_sep.html`
- `mibici/monitoring.py`
- `reports/resultados_mlflow_entrega2.md`

Los hallazgos de julio–agosto provienen de `resumen.md` y `resumen.json`; sus reportes HTML se generan con `--current sep jul_ago` y no se versionan por su tamaño.

Este documento corresponde exclusivamente a la interpretación de resultados del punto 3 y no modifica los modelos, el entrenamiento ni los reportes generados por Evidently.
