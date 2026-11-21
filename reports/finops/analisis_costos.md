# Análisis FinOps — Proyecto MiBici

**Entregable 7 — Punto 5: Análisis de costos por inferencia**
**Proyecto:** MiBici — Equipo 45
**Insumos:** [análisis de recursos](../recursos/analisis_recursos.md), pruebas de Locust y precios on-demand de AWS

> Versión 2 (21 de noviembre de 2026). La primera versión usaba una tarifa ilustrativa de
> USD 0.12/h y solo la configuración sin caché. Esta versión usa el precio publicado de una
> instancia real de AWS en dos regiones y las mediciones con y sin caché.

## 1. Objetivo

Estimar cuánto cuesta operar el servicio de predicción de MiBici y cuánto cuesta cada inferencia,
con base en el desempeño medido y el precio de una instancia de nube, y cuantificar las
opciones para reducir ese costo sin dejar de cumplir los límites de latencia y errores.

## 2. Supuestos de infraestructura

### 2.1. Instancia de referencia

Se supone un despliegue en una sola instancia EC2 que ejecuta el mismo `docker-compose.yml`:

| Necesidad según Compose | Valor |
|---|---|
| CPU asignada | API 2 + MLflow 1 = 3 vCPU |
| Memoria asignada | API 1 GiB + MLflow 1 GiB = 2 GiB, más el sistema operativo |

La instancia de referencia es **c6i.xlarge** (4 vCPU, 8 GiB, familia optimizada para cómputo), la más pequeña de su familia que cubre los 3 vCPU asignados con margen para el sistema.

### 2.2. Precios

Precios on-demand de Linux publicados por AWS (archivo de precios con fecha de publicación
2026-11-21, consultado el mismo día):

| Instancia | vCPU / memoria | us-east-1 (N. Virginia) | mx-central-1 (México) |
|---|---|---:|---:|
| **c6i.xlarge** | 4 / 8 GiB | **USD 0.1700/h** | **USD 0.1785/h** |
| t3.large (alternativa, sección 7.2) | 2 / 8 GiB | USD 0.0832/h | USD 0.0874/h |

Se comparan dos regiones: us-east-1, la de referencia más común y la más barata, y mx-central-1,
la más cercana a los usuarios de MiBici en Guadalajara.

**No se incluye:** almacenamiento EBS, transferencia de datos, balanceador, IP pública,
monitoreo administrado, respaldos ni impuestos. Un mes equivale a 730 horas.

## 3. Desempeño medido

Se cuentan como **inferencias válidas** solo las predicciones de P1 y P2. `/health` y las
peticiones inválidas que deben responder 422 no cuentan.

| Configuración | Escenario | Usuarios | RPS total | RPS P1 | RPS P2 | Inferencias válidas/s | p95 | ¿Cumple? |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Con caché | baseline | 5 | 14.16 | 7.40 | 4.36 | 11.76 | 53 ms | sí |
| Con caché | carga | 25 | 71.07 | 35.63 | 21.55 | 57.18 | 55 ms | sí |
| Con caché | estrés | 100 | 211.27 | 104.73 | 64.25 | 168.98 | 410 ms | sí |
| Sin caché | baseline | 5 | 3.89 | 1.84 | 1.08 | 2.92 | 2,100 ms | no |
| Sin caché | carga | 25 | 2.24 | 1.10 | 0.63 | 1.73 | 22,000 ms | no |
| Sin caché | estrés | 100 | 2.17 | 0.94 | 0.61 | 1.55 | 73,000 ms | no |

Límites de aceptación: p95 ≤ 500 ms y errores ≤ 1 %. Ningún escenario tuvo errores.

## 4. Modelo de costos

```text
Costo por 1,000 inferencias = Precio por hora / (Inferencias válidas por segundo × 3,600) × 1,000
```

El costo de la instancia es fijo por hora: no depende de cuántas inferencias se atiendan. Por eso
el costo unitario depende por completo de cuánto se use la capacidad.

### 4.1. Costo por 1,000 inferencias en c6i.xlarge

| Configuración | Escenario | Inferencias/hora | us-east-1 (USD) | mx-central-1 (USD) | ¿Capacidad válida? |
|---|---|---:|---:|---:|---|
| Con caché | baseline | 42,336 | 0.00402 | 0.00422 | sí |
| Con caché | carga | 205,848 | 0.00083 | 0.00087 | sí |
| Con caché | **estrés** | **608,328** | **0.00028** | **0.00029** | **sí (máximo medido)** |
| Sin caché | baseline | 10,512 | 0.01617 | 0.01698 | no |
| Sin caché | carga | 6,228 | 0.02730 | 0.02866 | no |
| Sin caché | estrés | 5,580 | 0.03047 | 0.03199 | no |

En baseline y carga el número de inferencias lo limita la cantidad de usuarios simulados, no el
servidor. La **capacidad válida** es el mayor rendimiento que todavía cumple los límites: con caché,
**169 inferencias/s** (escenario de estrés). Sin caché ningún escenario cumple, así que no existe
una capacidad válida; sus costos solo sirven para comparar.

### 4.2. Costo por periodo de la instancia

| Periodo | us-east-1 (USD) | mx-central-1 (USD) |
|---|---:|---:|
| 1 hora | 0.17 | 0.18 |
| 1 día (24 h) | 4.08 | 4.28 |
| 1 mes (730 h) | **124.10** | **130.31** |

## 5. Costo y desempeño: el efecto de la caché

Con el mismo costo por hora, la caché multiplica la capacidad por ~58 (168.98 frente a 2.92
inferencias/s, comparando el máximo rendimiento de cada configuración) y es la única configuración
que cumple los límites. Comparando el mismo escenario baseline, el costo por 1,000 inferencias
baja de USD 0.01617 a USD 0.00402 en us-east-1, 4 veces menos, aunque en baseline la caché ni
siquiera está aprovechada. Es la optimización FinOps de mayor efecto en este proyecto y ya está
desplegada (PR #27).

## 6. Demanda real frente a capacidad

La capacidad medida no es la demanda. Una estimación de la demanda real:

- MiBici tiene **480 estaciones** válidas en el catálogo.
- Si cada hora se predicen la demanda (P1) y el riesgo (P2) de cada estación, son
  480 × 24 × 2 = **23,040 inferencias diarias**, en promedio **0.27 inferencias/s**.

| Indicador | us-east-1 | mx-central-1 |
|---|---:|---:|
| Uso de la capacidad válida (0.27 / 169 inferencias/s) | 0.16 % | 0.16 % |
| Costo diario de la instancia | USD 4.08 | USD 4.28 |
| **Costo efectivo por 1,000 inferencias** | **USD 0.177** | **USD 0.186** |

Con esa demanda, cada inferencia cuesta unas **630 veces más** que en el escenario de estrés
(USD 0.177 frente a 0.00028 por 1,000), porque se paga una instancia que pasa casi todo el tiempo
sin trabajo. Es un supuesto: el volumen real depende de cómo se integre la API (paneles, apps,
consultas de usuarios). Sirve para mostrar que **el costo lo domina la capacidad ociosa, no el
cómputo por inferencia**.

## 7. Oportunidades de optimización

### 7.1. Mantener la caché (ya aplicada)

Sin caché, la misma instancia no cumple los límites con ningún número de usuarios. Con caché
cumple hasta 169 inferencias/s. Debe tratarse como requisito del despliegue.

### 7.2. Ajustar el tamaño de la instancia

Lo que se usó de verdad, con caché y en el peor escenario (estrés):

| Recurso | Asignado en Compose | Usado (máximo) |
|---|---:|---:|
| CPU de la API | 2 vCPU | 1.38 vCPU |
| CPU de MLflow | 1 vCPU | 0.11 vCPU |
| Memoria de la API | 1 GiB | 231 MiB |
| Memoria de MLflow | 1 GiB | 1,024 MiB (en el límite) |

El servicio necesita menos de 2 vCPU y unos 2 GiB de memoria si MLflow recibe el margen
recomendado (1.5 GiB). Una **t3.large** (2 vCPU, 8 GiB) lo cubre:

| Instancia | us-east-1 / mes | mx-central-1 / mes | Ahorro frente a c6i.xlarge |
|---|---:|---:|---:|
| c6i.xlarge | USD 124.10 | USD 130.31 | — |
| t3.large | USD 60.74 | USD 63.80 | **51 %** |

Condición: las instancias t3 son de rendimiento ampliable. Trabajan por debajo de un nivel base
de CPU y acumulan créditos para picos, así que una carga sostenida como la del escenario de
estrés agotaría los créditos. Con la demanda estimada (sección 6) la CPU queda muy por debajo de
ese nivel. Antes de cambiar hay que medir en la propia t3.large, porque las mediciones se hicieron
en un procesador de escritorio más rápido por núcleo.

### 7.3. Encender solo cuando se necesita

El costo es por hora encendida. Si el servicio solo se ofrece en un horario, por ejemplo 12 h al
día, el costo mensual baja a la mitad:

| Instancia | 24 h/día (us-east-1 / mx-central-1) | 12 h/día (us-east-1 / mx-central-1) |
|---|---:|---:|
| c6i.xlarge | USD 124.10 / 130.31 | USD 62.05 / 65.15 |
| t3.large | USD 60.74 / 63.80 | USD 30.37 / 31.90 |

Si las predicciones se generan una vez por hora para todas las estaciones, una alternativa todavía
más barata es correrlas como trabajo por lotes y guardar los resultados, en lugar de mantener una
API encendida.

### 7.4. Elegir la región

mx-central-1 cuesta 5 % más que us-east-1 (USD 6.21 más al mes con c6i.xlarge). A cambio queda
más cerca de los usuarios en Guadalajara. Con latencias de servicio de decenas de milisegundos,
la región conviene elegirla por cercanía o por requisitos de residencia de datos, no por precio.

### 7.5. Compromisos de uso

Las instancias reservadas y los Savings Plans de AWS reducen la tarifa por hora a cambio de un
compromiso de uno a tres años. No se cuantifican aquí porque no se consultaron sus precios. Solo
convienen si el servicio va a estar encendido de forma continua.

### 7.6. Métricas para monitorear el costo

- Inferencias válidas por hora y uso de la capacidad válida.
- Costo por 1,000 inferencias efectivo (con la demanda real, no la de prueba).
- p95 y tasa de errores, para no optimizar costo a costa de los límites.
- CPU de la API y memoria de MLflow, que son los recursos que deciden el tamaño de la instancia.

## 8. Limitaciones

1. Una sola corrida por configuración, en Podman sobre WSL2 y con Locust en el mismo equipo (ver
   las limitaciones del [análisis de recursos](../recursos/analisis_recursos.md#8-limitaciones)).
2. La capacidad medida en un Intel Core Ultra 9 de escritorio no equivale a la de una c6i.xlarge
   ni a la de una t3.large; hay que confirmarla con una prueba en la instancia elegida.
3. Las pruebas duraron 60 a 120 s. Extrapolarlas a horas supone que el rendimiento se sostiene.
4. La demanda real (sección 6) es una estimación por estaciones y horas, no un registro de uso.
5. Solo se considera el cómputo on-demand. Faltan almacenamiento, red, monitoreo e impuestos.

## 9. Conclusión

En una c6i.xlarge el servicio cuesta USD 124.10 al mes en us-east-1 y USD 130.31 en mx-central-1.
Con caché atiende hasta 169 inferencias válidas por segundo cumpliendo los límites, lo que en
capacidad plena equivale a USD 0.00028–0.00029 por cada 1,000 inferencias. Sin caché ninguna
carga cumple los límites, así que la caché es la decisión de costo más importante y ya está
aplicada.

Con la demanda estimada de MiBici (23,040 inferencias diarias) la instancia se usaría al 0.16 %,
y el costo efectivo sería de USD 0.18–0.19 por 1,000 inferencias. Por eso la siguiente
optimización no es acelerar la inferencia, sino **pagar menos capacidad ociosa**: pasar a una
t3.large (−51 %), encender el servicio solo cuando se necesita (−50 %) o generar las predicciones
por lotes. Cualquier cambio debe validarse con una prueba de carga en la instancia elegida y con
el límite de memoria de MLflow corregido.

**La recomendación FinOps es optimizar el costo sujeto a cumplir los límites de desempeño, no
minimizar el costo por inferencia de forma aislada.**

## 10. Evidencia y fuentes

- Mediciones: `reports/recursos/con_cache/` y `reports/recursos/sin_cache/`.
- [Análisis de recursos](../recursos/analisis_recursos.md).
- `docker-compose.yml` (límites de CPU y memoria).
- Precios on-demand de AWS EC2 para Linux, us-east-1 y mx-central-1 (publicación 2026-11-21):
  [Amazon EC2 On-Demand Pricing](https://aws.amazon.com/ec2/pricing/on-demand/).
- Número de estaciones: catálogo de la ingesta descrito en el `README.md`.

Este análisis no modifica la API, los modelos registrados ni los escenarios de Locust.
