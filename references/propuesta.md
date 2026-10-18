# Propuesta de solución | Equipo 45

Este documento precisa el diseño del Canvas inicial. La ingesta y el módulo de variables ya están implementados; el entrenamiento P1-P3 y el registro en MLflow están implementados. El protocolo de evaluación se fija antes de ejecutar la prueba final. Resultados de datos y comprobaciones: [ingesta_features.md](ingesta_features.md).

## 1. Problemas y decisiones

La unidad de análisis es una estación. P1 y P2 se calculan al inicio de cada hora local `t`, para `[t, t + 1 hora)`, utilizando únicamente información anterior a `t`. Un viaje en curso no cuenta como llegada antes de finalizar.

| Pregunta | Objetivo y alcance | Usuario y decisión |
|---|---|---|
| P1: regresión | Número de viajes iniciados en cada estación durante la siguiente hora. | El operador anticipa demanda y planea la distribución de la flota. |
| P2: clasificación | Riesgo aproximado al cierre de la siguiente hora: normal, falta de bicicletas o falta de anclajes. | Rebalanceo prioriza estaciones para inspección y movimiento de bicicletas. |
| P3: clustering | Tres grupos iniciales por perfil horario de salidas, con ubicación en un mapa. | Planeación identifica patrones y estudia zonas de servicio. |

P1 y P2 se recalcularían cada hora. P3 se construye con entrenamiento, se contrasta con validación y se propone actualizar mensualmente. Las coordenadas sirven para localizar los grupos, sin imponer proximidad geográfica al agrupar comportamientos.

## 2. Datos propuestos

- **Fuente:** [portal de MiBici](https://www.mibici.net/es/datos-abiertos/). Se proponen nueve meses completos, enero-septiembre de 2026, para incluir variaciones semanales y mensuales. No representan un ciclo anual completo.
- **Archivos:** CSV `datos_abiertos_AAAA_MM.csv` y catálogo de septiembre. Enlaces publicados: [enero](https://www.mibici.net/site/assets/files/120163/datos_abiertos_2026_01.csv), [septiembre](https://www.mibici.net/site/assets/files/131825/datos_abiertos_2026_09.csv) y [catálogo](https://www.mibici.net/site/assets/files/1118/nomenclatura_2026_09.csv). La ingesta resolvió los nueve enlaces desde el portal y conserva las URL en el manifiesto.
- **Variables originales:** ID del viaje para deduplicación, inicio, fin, origen y destino; del catálogo, ID, nombre, capacidad, latitud y longitud. Los tipos y alias se verifican al descargar; el notebook documenta el esquema limpio.
- **Tamaño real:** nueve meses, 3,362,065 registros originales y 3,358,273 viajes válidos; 471 IDs observados y 480 estaciones en el catálogo. Descartes: 3,034 registros inválidos y 758 duplicados. El [manifiesto](data_manifest.json) conserva cifras por archivo y hashes. No son contadores globales del portal.
- **Privacidad:** excluir identificadores de usuarios, edad, género y otros atributos personales de las tablas de modelado. El ID del viaje es un control local de calidad, no un predictor. Artefactos y mapas mostrarán agregados por estación/hora.
- **Condiciones de uso:** se revisaron el portal, sus [términos](https://www.mibici.net/es/termino-y-condiciones/) y el [aviso de privacidad](https://www.mibici.net/es/aviso-de-privacidad/) el 18 de octubre de 2026. No se identificó una licencia específica de redistribución de los CSV; no se atribuye MIT a los datos. La entrega usa agregados y excluye los archivos por viaje. Ver [condiciones_datos.md](condiciones_datos.md).

## 3. Partición y disponibilidad temporal

Las fechas y parámetros se centralizan en `mibici/config.py`.

| Conjunto | Periodo | Propósito |
|---|---|---|
| Entrenamiento | Enero-junio de 2026 | Ajustar transformaciones y modelos. |
| Validación | Julio-agosto de 2026 | Elegir parámetros y revisar sensibilidad. |
| Prueba | Septiembre de 2026 | Una evaluación final tras fijar decisiones. |

Los intervalos incluyen inicio y excluyen fin. Se descartan filas cuyo horizonte cruza un corte y el inicio sin historia suficiente. No se mezclan filas aleatoriamente. Imputación, escalado y parámetros se ajustan solo con entrenamiento. Los rezagos y medias excluyen la hora objetivo.

La evaluación de P1-P2 simula predicciones consecutivas a una hora. Puede usar observaciones previas ya conocidas de validación/prueba, sin reentrenar ni utilizar observaciones de la hora objetivo. No equivale a pronosticar un mes desde una fecha única.

El catálogo de septiembre es un metadato fijo del ejercicio retrospectivo: no demuestra capacidad histórica ni fechas de alta. Se marcarán estaciones sin correspondencia y cambios detectables. La capacidad posterior se excluye como predictor de P1. P2 necesitará capacidad histórica e inventarios para una validación operativa. Las horas sin viajes se completarán con cero únicamente dentro de periodos de cobertura y actividad de estación justificados.

## 4. Proxy explícito para P2

No hay inventarios publicados. Se define una **ocupación virtual**, cuya etiqueta no demuestra que una estación estuvo vacía o llena.

1. Para capacidad positiva `C`, inicializar cada estación con `q0 = 0.5 * C` al inicio de los datos.
2. Ordenar eventos: salida al comenzar un viaje y llegada al terminarlo. Agregar eventos simultáneos y actualizar `q = clip(q + llegadas - salidas, 0, C)`.
3. Al predecir en `t`, usar solamente el estado construido con eventos anteriores a `t`. Mantenerlo entre meses y particiones, sin reinicios informados por resultados futuros.
4. Etiquetar el estado al cierre de la siguiente hora: riesgo sin bicicletas si `q/C <= 0.10`; riesgo sin anclajes si `q/C >= 0.90`; normal en otro caso.
5. Revisar sensibilidad en validación con ocupación inicial de 25%, 50% y 75%, manteniendo umbrales fijos.

El margen de 10% es una hipótesis para anticipar desbalances, no un umbral validado por el operador. Se mide el cierre de la hora; podría omitirse un desbalance transitorio.

La simulación omite rebalanceos, averías y capacidad histórica; el recorte puede ocultar flujos físicamente incompatibles. Las métricas medirán concordancia con este escenario, no disponibilidad real. No se propondrán acciones automáticas de rebalanceo con esta evidencia.

## 5. Pipelines, baselines, candidatos y métricas

### P1 | Demanda

**Pipeline:** CSV normalizado -> duplicados/fechas -> conteos por estación/hora -> calendario, rezagos 1/24/168 h y medias 24/168 h -> partición temporal -> ajuste -> evaluación. Rezagos y medias describen persistencia y ciclos, siempre antes de la hora objetivo.

**Baseline:** misma estación/hora de la semana anterior. Sin historia, promedio por estación y hora de la semana aprendido en entrenamiento; para estación no vista, promedio global de entrenamiento. **Candidato:** `HistGradientBoostingRegressor(loss="poisson")`, por tratarse de conteos no negativos con posibles relaciones no lineales.

**Métricas:** MAE principal, RMSE para errores grandes y WAPE global, `sum(abs(y - pred)) / sum(y)`. Con demanda total cero, WAPE se reporta como no definida. No se elige MAPE por las horas con cero viajes. Nombres: `val_mae`, `val_rmse`, `val_wape`; prefijo `test_` para prueba final.

### P2 | Riesgo virtual

**Pipeline:** viajes válidos -> eventos/flujo -> estado virtual causal -> etiqueta futura -> calendario, ocupación virtual y flujos históricos -> partición temporal -> escalado ajustado en entrenamiento (las tablas verificadas no contienen faltantes en los predictores) -> clasificador -> evaluación.

Se excluyen el flujo y estado de la hora objetivo. P2 no usará predicciones de P1 en esta versión: integrarlas exigiría obtener predicciones temporales fuera de muestra.

**Baseline:** `LogisticRegression(class_weight="balanced", max_iter=1000)` de tres clases. **Candidato:** `HistGradientBoostingClassifier`, con pesos calculados solo en entrenamiento.

**Métricas:** F1 macro principal, balanced accuracy y precisión/recall por clase, para atender ambos tipos de riesgo. Se propone average precision macro uno contra el resto, distinguiéndola del área trapezoidal PR. Si faltan positivos o una clase de entrenamiento, se reportará la limitación y la métrica no definida, sin inventar ceros. Métricas con prefijos `val_`/`test_` y matriz de confusión como artefacto.

### P3 | Patrones de uso

**Pipeline:** salidas por hora -> 48 componentes por estación (24 horas laborales y 24 de fin de semana), usando medias por día observado -> normalización del perfil -> agrupación -> evaluación y mapa. Se reportarán aparte estaciones con perfil nulo o cobertura insuficiente.

Normalizar evita que el volumen total domine la forma del patrón. Las coordenadas solo se usarán para el mapa.

**Baseline:** `KMeans(n_clusters=3, n_init=10, random_state=SEED)`. **Candidato:** `AgglomerativeClustering(n_clusters=3, linkage="ward")`. Tres grupos es una hipótesis interpretable inicial, no un resultado descubierto.

**Métricas:** silhouette (mayor), Davies-Bouldin (menor), tamaño de grupos y adjusted Rand index entre agrupaciones de perfiles de entrenamiento y validación, solo en estaciones comunes. Registrar exclusiones. Los nombres serán `train_silhouette`, `train_davies_bouldin` y `val_ari`. Las métricas internas requieren al menos dos grupos y menos grupos que estaciones. El mapa y los perfiles complementan los números.

## 6. Arquitectura y registro propuestos

El [diagrama](arquitectura.svg) y su [justificación](arquitectura.md) separan fuentes, ingesta, almacenamiento, variables, entrenamiento y seguimiento. Se propone Parquet mensual, manifiesto SHA-256 y MLflow local con SQLite.

Los runs registrarán equipo, P1/P2/P3 y commit; rango/cortes, versión del manifiesto, semilla y parámetros; métricas con prefijo y artefactos. Nombres propuestos: `P1_estacional_h1`, `P2_logistica_proxy_h1`, `P3_kmeans_perfil48`. Se compararán además dos configuraciones de una misma pregunta, sin contrastar directamente métricas de tareas diferentes.

## Referencias

DrivenData. (s. f.). *Cookiecutter Data Science*. https://cookiecutter-data-science.drivendata.org/

Huyen, C. (2022). *Designing machine learning systems: An iterative process for production-ready applications*. O'Reilly Media. https://www.oreilly.com/library/view/designing-machine-learning/9781098107956/

MiBici. (s. f.). *Datos abiertos* [Conjunto de datos]. https://www.mibici.net/es/datos-abiertos/

MLflow. (s. f.). *MLflow Tracking* [Documentación]. https://mlflow.org/docs/latest/ml/tracking/

Scikit-learn developers. (s. f.). *Metrics and scoring: Quantifying the quality of predictions*. https://scikit-learn.org/stable/modules/model_evaluation.html

Treveil, M., Omont, N., Stenac, C., Lefevre, K., Phan, D., Zentici, J., Lavoillotte, A., Miyazaki, M., & Heidmann, L. (2020). *Introducing MLOps: How to scale machine learning in the enterprise*. O'Reilly Media.
