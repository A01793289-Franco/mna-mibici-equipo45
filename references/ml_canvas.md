# Machine Learning Canvas | Equipo 45

Fuente editable del contenido. El PDF conserva la distribución y los iconos de la plantilla original. Los experimentos se ejecutaron en dos iteraciones (véase [resultados_mlflow.md](../reports/resultados_mlflow.md)); se documenta el diseño de monitoreo operativo.

## Decisión

**P1:** Cuántas bicicletas disponer por estación y periodo.

**P2:** Qué estaciones revisar y priorizar para rebalanceo.

**P3:** Qué estaciones comparten patrones de uso y dónde se ubican.

## Tarea de predicción

**P1:** Viajes iniciados por estación en la siguiente hora (regresión).

**P2:** Riesgo virtual al cierre de esa hora: normal, sin bicicletas o sin anclajes.

**P3:** Tres grupos por perfil horario de uso. Coordenadas solo para el mapa.

## Propuesta de valor

**P1:** El operador anticipa demanda para distribuir la flota.

**P2:** Rebalanceo prioriza estaciones con riesgo virtual. El proxy no representa inventario real.

**P3:** Planeación interpreta patrones y ubicación para estudiar cobertura.

## Fuentes de datos

CSV mensuales de viajes: enero-septiembre de 2026. Catálogo: nomenclatura_2026_09.csv.

Inicio y fin, estaciones e ID del viaje para deduplicar; capacidad y coordenadas del catálogo.

3,358,273 viajes válidos; 471 IDs observados. Sin atributos personales. Licencia específica de los CSV no identificada.

## Recolección de datos

Ingesta ejecutada: descarga, normalización de columnas y fechas; revisión de duplicados y registros inválidos.

CSV crudo local y Parquet mensual. Manifiesto en Git con URL, SHA-256 y conteos.

Enero-septiembre 2026: nueve meses verificados.

## Predicciones

**P1 y P2:** cada hora, usando solo eventos anteriores a la predicción.

**Proxy P2:** iniciar al 50% de capacidad; acumular llegadas finalizadas menos salidas y recortar entre cero y capacidad.

Umbrales: 10% y 90%. Ocupación inicial utilizada: 50%.

**P3:** análisis por lotes con actualización mensual propuesta.

Runs reales en MLflow en dos iteraciones; modelos `champion` en Model Registry. P1-P2 tienen una evaluación original de septiembre en la primera iteración y una comparación retrospectiva de sus finalistas en la ejecución definitiva de la segunda. La elección sigue usando validación y P3 no usa septiembre.

## Evaluación Offline

Entrenar: enero-junio. Validar: julio-agosto. Prueba: septiembre. Excluir horizontes que cruzan cortes.

**P1:** MAE, RMSE y WAPE.

**P2:** F1 macro, balanced accuracy, precisión/recall por clase y AP macro.

**P3:** silhouette, Davies-Bouldin, mapa/tamaños y ARI en validación.

## Ingeniería de características

**P1:** calendario; rezagos 1/24/168 h y medias 24/168 h, sin hora objetivo.

**P2:** calendario, ocupación virtual y flujo histórico. Sin predicciones de P1.

**P3:** 48 medias horarias laborable/fin de semana, normalizadas.

Catálogo posterior fijo: limitación retrospectiva documentada.

## Construcción de modelos

**P1:** baseline estacional (semana anterior). Candidato: gradient boosting para conteos.

**P2:** baseline de regresión logística balanceada. Candidato: gradient boosting.

**P3:** baseline K-means (k=3, semilla fija). Candidato: jerárquico Ward (k=3).

Rutas, fechas y parámetros centralizados en mibici/config.py.

Detalle de modelos, métricas y supuestos en propuesta.md.

## Evaluación en vivo y monitoreo

Comparar predicciones y observaciones por estación. Vigilar deriva, nuevas estaciones, cambios de capacidad y calidad de datos.

Diseño de monitoreo: contrastar disponibilidad e inventarios del operador. MLflow liga pregunta, versiones y commit. P2 evalúa un estado virtual.

Las fórmulas, los supuestos, las métricas y las referencias están en [propuesta.md](propuesta.md). Estructura conceptual: [Machine Learning Canvas, Louis Dorard](https://www.louisdorard.com/machine-learning-canvas/).
