# Análisis FinOps — Proyecto MiBici

**Entregable 7 — Punto 5: Análisis de costos por inferencia**  
**Proyecto:** MiBici — Equipo 45  
**Herramientas:** Docker Compose, Docker Stats y Locust

## 1. Objetivo

Estimar el costo de operación de los servicios de predicción de MiBici y el costo unitario por inferencia, utilizando los resultados de rendimiento y consumo de recursos disponibles.

El propósito es identificar oportunidades de optimización económica sin comprometer los objetivos de latencia y disponibilidad del sistema.

## 2. Infraestructura evaluada

El proyecto utiliza dos servicios principales:

| Servicio | CPU configurada | Memoria máxima |
|---|---:|---:|
| API de predicción | 2 CPU | 1 GiB |
| MLflow | 1 CPU | 1 GiB |

Los recursos corresponden a límites configurados en Docker Compose, no a capacidad reservada ni a consumo continuo demostrado.

Para efectos de este ejercicio se utiliza una tarifa ilustrativa de **USD 0.12/hora** para la infraestructura conjunta.

Este valor es un supuesto académico y no corresponde a una cotización verificada de un proveedor de nube.

La estimación no incluye almacenamiento adicional, transferencia de datos, impuestos, monitoreo administrado ni otros posibles cargos.

## 3. Resultados de rendimiento

Se utilizan los reportes de Locust de la configuración sin caché.

| Escenario | Usuarios | RPS global | RPS P1 | RPS P2 | RPS de inferencias válidas |
|---|---:|---:|---:|---:|---:|
| Baseline | 5 | 11.14 | 5.70 | 3.31 | 9.01 |
| Carga | 25 | 51.79 | 25.48 | 15.86 | 41.34 |
| Estrés | 100 | 97.50 | 48.15 | 29.99 | 78.14 |

Las solicitudes `/health` y las entradas inválidas se excluyen del conteo de inferencias válidas.

Los RPS proceden de los reportes originales y presentan redondeos.

## 4. Modelo de costos

Se aplica la siguiente fórmula:

**Costo por inferencia = Costo de infraestructura por hora / Inferencias por hora**

Donde:

**Inferencias por hora = Inferencias válidas por segundo × 3,600**

Se supone que el rendimiento medido puede sostenerse durante una hora, lo cual no ha sido demostrado mediante pruebas prolongadas.

### 4.1. Comparación económica por escenario

| Escenario | Inferencias/hora estimadas | Costo por 1,000 inferencias (USD) |
|---|---:|---:|
| Baseline | 32,436 | 0.00370 |
| Carga | 148,824 | 0.00081 |
| Estrés | 281,304 | 0.00043 |

Todos los escenarios utilizan el mismo supuesto de USD 0.12/hora.

El menor costo unitario aparente bajo estrés se debe al mayor volumen procesado. No implica que ese escenario sea recomendable para producción.

### 4.2. Costo por periodo

Suponiendo infraestructura encendida continuamente:

| Periodo | Costo estimado (USD) |
|---|---:|
| 1 hora | 0.12 |
| 24 horas | 2.88 |
| 30 días | 86.40 |

Estos costos corresponden al tiempo de infraestructura encendida, independientemente de cuántas inferencias se soliciten.

## 5. Relación entre costo y desempeño

El objetivo de aceptación del proyecto establece:

- Latencia p95 global menor o igual a 500 ms.
- Tasa de errores menor o igual a 1 %.

Los resultados de las pruebas sin caché son:

| Escenario | p95 global | Errores | Cumplimiento |
|---|---:|---:|---|
| Baseline | 320 ms | 0 % | Cumple |
| Carga | 680 ms | 0 % | No cumple |
| Estrés | 590 ms | 0 % | No cumple |

Aunque los escenarios de carga y estrés producen un costo unitario matemáticamente inferior, incumplen el objetivo de latencia.

Por tanto, **no deben utilizarse como capacidad validada para producción**.

El escenario baseline es el único de estos tres que satisface ambos criterios, aunque una prueba de 60 segundos no demuestra sostenibilidad operativa prolongada.

## 6. Relación con el consumo de recursos

Los registros de Docker Stats muestran los siguientes valores de memoria:

| Escenario | API | MLflow |
|---|---:|---:|
| Baseline | 81.12 % | 98.59 % |
| Carga | 93.54 % | 98.62 % |
| Estrés | 98.52 % | 98.56 % |

La elevada utilización de memoria indica que la infraestructura debe dimensionarse cuidadosamente.

Los porcentajes corresponden a capturas puntuales. No permiten demostrar por sí mismos saturación continua, fallos de memoria o necesidades exactas de ampliación.

Tampoco es correcto dimensionar la infraestructura únicamente a partir de los porcentajes instantáneos de CPU disponibles.

## 7. Oportunidades de optimización FinOps

### 7.1. Optimización de memoria

Investigar el consumo de memoria de la API y MLflow antes de incrementar la capacidad de infraestructura.

Evaluar posibles mejoras en carga de modelos, concurrencia y configuración de procesos.

### 7.2. Uso de caché

Comparar las configuraciones con y sin caché bajo condiciones equivalentes.

La caché puede reducir operaciones repetidas, pero su beneficio económico debe verificarse considerando también el consumo adicional de memoria.

### 7.3. Dimensionamiento adecuado

Seleccionar infraestructura que cumpla los objetivos de latencia y errores con margen de seguridad.

Evitar elegir la configuración exclusivamente por el menor costo calculado por inferencia.

### 7.4. Demanda real y utilización

Registrar el volumen real de inferencias por hora y los periodos de baja actividad.

El costo efectivo por inferencia depende de la utilización real del servicio, no únicamente de su capacidad máxima observada.

### 7.5. Monitoreo financiero

Registrar periódicamente:

- Costo de infraestructura por hora.
- Inferencias válidas por hora.
- Costo por 1,000 inferencias.
- Latencia p95 y tasa de errores.
- Consumo de CPU y memoria.
- Diferencias de costo entre configuraciones.

## 8. Limitaciones

1. El precio de USD 0.12/hora es hipotético.
2. Los resultados de Locust corresponden a pruebas de corta duración.
3. Los valores de rendimiento se extrapolan para estimar inferencias por hora.
4. No se incluye el costo de todos los servicios que podría requerir un despliegue real.
5. Las mediciones de Docker Stats son instantáneas.
6. Los escenarios de carga y estrés incumplen el objetivo de latencia.
7. No se ha realizado una medición de facturación real ni una prueba de capacidad sostenida.

Para convertir este ejercicio en una estimación de nube verificable, será necesario seleccionar proveedor, región, tipo de instancia, tarifa vigente y arquitectura de despliegue.

## 9. Conclusión

El análisis FinOps permite relacionar el rendimiento del sistema MiBici con un costo estimado de infraestructura.

Bajo el supuesto de USD 0.12/hora, el escenario de carga presenta un costo teórico aproximado de USD 0.00081 por cada 1,000 inferencias válidas.

Sin embargo, dicho escenario incumple el objetivo de latencia p95. Por tanto, su costo unitario no debe interpretarse como una configuración operativa recomendada.

El escenario baseline cumple los criterios establecidos en la prueba realizada y presenta un costo estimado de USD 0.00370 por cada 1,000 inferencias, bajo el mismo supuesto.

Se recomienda mejorar el monitoreo continuo, investigar el uso elevado de memoria y realizar comparaciones controladas entre configuraciones antes de definir una infraestructura de producción.

**La recomendación FinOps es optimizar el costo sujeto al cumplimiento de los requisitos de desempeño, no minimizar el costo por inferencia de manera aislada.**

## 10. Evidencia

- `docker-compose.yml`
- `reports/carga_sin_cache/baseline/resumen.md`
- `reports/carga_sin_cache/carga/resumen.md`
- `reports/carga_sin_cache/estres/resumen.md`
- `reports/carga_sin_cache/baseline/docker_stats.txt`
- `reports/carga_sin_cache/carga/docker_stats.txt`
- `reports/carga_sin_cache/estres/docker_stats.txt`
- `reports/recursos/analisis_recursos.md`

Este análisis no modifica la API, los modelos registrados ni los escenarios originales de Locust.
