# Análisis de consumo de recursos — MiBici

**Entregable 7 — Punto 4: Monitoreo de recursos**
**Proyecto:** MiBici — Equipo 45
**Herramientas:** `podman stats` (muestreo continuo con `mibici.resource_monitor`) y Locust
**Escenarios:** reposo, baseline, carga y estrés; con caché (configuración desplegada) y sin caché

> Versión 2 (21 de noviembre de 2026). La primera versión interpretaba una captura de
> `docker stats` tomada al terminar cada prueba, solo sin caché. Esta versión mide durante
> toda la prueba, incluye la configuración con caché que hoy se despliega y agrega el
> consumo en reposo.

## 1. Objetivo

Medir el consumo de CPU y memoria de la API de predicción y de MLflow mientras Locust genera
carga, para identificar qué recurso limita la capacidad, qué margen queda y qué parte de la
infraestructura sobra o falta. Estos resultados alimentan el [análisis FinOps](../finops/analisis_costos.md).

## 2. Metodología

### 2.1. Configuraciones comparadas

| Configuración | Imagen | Comportamiento |
|---|---|---|
| **Con caché** | `main` actual (`11061b2`) | El champion se carga una vez y se conserva en memoria 300 s (`MODEL_CACHE_SECONDS`). Es lo que se despliega. |
| **Sin caché** | `f643a07`, último commit antes del PR #27 | Cada petición consulta MLflow, descarga y carga el modelo. Solo cambia `mibici/api.py`. |

Para "sin caché" se usó la imagen anterior al PR #27 y no `MODEL_CACHE_SECONDS=0` con el código
actual: en el código actual las recargas pasan por un candado por pregunta y no reproducen el
comportamiento anterior. En esta medición ambas variantes dieron un rendimiento parecido
(~3 RPS), pero la imagen previa es la que representa la versión que existió.

### 2.2. Procedimiento

- `docker-compose.yml` sin cambios: API con 2 CPU y 1 GiB; MLflow con 1 CPU y 1 GiB.
- Antes de cada escenario se recrearon los contenedores (`compose down` / `up --wait`), para que
  ningún escenario herede memoria o modelos cargados del anterior.
- Reposo: 60 s sin tráfico. Baseline: 5 usuarios, 60 s. Carga: 25 usuarios, 120 s. Estrés:
  100 usuarios, 120 s. Mismo `load/locustfile.py` y mismos límites de aceptación (p95 ≤ 500 ms,
  errores ≤ 1 %).
- `python -m mibici.load_test --stats podman` lee `podman stats` cada 2 s durante toda la prueba
  (29 a 61 muestras por servicio y escenario) y resume media, p95 y máximo.
- Podman reporta con `--no-stream` el % de CPU promedio desde que arrancó el contenedor. Por eso
  la CPU se calcula entre dos lecturas consecutivas del contador acumulado de CPU (`CPUNano`); se
  comprobó que un proceso que ocupa un núcleo da ~100 %. La CPU se expresa en % de un núcleo: el
  límite de la API equivale a 200 % y el de MLflow a 100 %.

### 2.3. Entorno

| Elemento | Valor |
|---|---|
| Equipo | Intel Core Ultra 9 275HX (24 núcleos), 31.4 GiB de RAM, Windows 11 |
| Contenedores | Podman 6.1.4 (máquina WSL2 con 24 CPU y 15.3 GiB) + Docker Compose 5.7.0 |
| Carga | Locust 2.46.0 en el mismo equipo |
| Modelos | `mibici-p1-demanda` v1 y `mibici-p2-riesgo` v1 (champion), exportados con `mibici.registry_bundle` |

## 3. Resultados de desempeño

| Configuración | Escenario | Peticiones | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Errores | Límites |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Con caché | baseline | 838 | 14.16 | 48 | 53 | 56 | 0 % | cumple |
| Con caché | carga | 8,474 | 71.07 | 47 | 55 | 62 | 0 % | cumple |
| Con caché | estrés | 25,187 | 211.27 | 130 | 410 | 520 | 0 % | cumple |
| Sin caché | baseline | 230 | 3.89 | 960 | 2,100 | 2,400 | 0 % | **no cumple** |
| Sin caché | carga | 266 | 2.24 | 9,600 | 22,000 | 24,000 | 0 % | **no cumple** |
| Sin caché | estrés | 256 | 2.17 | 23,000 | 73,000 | 75,000 | 0 % | **no cumple** |

Con caché los tres escenarios cumplen; en estrés el p95 (410 ms) deja un margen de 18 % respecto
al límite. Sin caché el servicio atiende alrededor de 2 a 4 peticiones por segundo sin importar
cuántos usuarios haya: lo que crece es la cola, y con ella la latencia.

## 4. Resultados de recursos

### 4.1. API de predicción (límite: 200 % de CPU, 1,024 MiB)

| Configuración | Escenario | CPU media | CPU p95 | CPU máx | Memoria media (MiB) | Memoria máx (MiB) | Memoria máx (%) | PIDS máx |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Con caché | reposo | 0.5 % | 2.3 % | 2.3 % | 187.6 | 188.8 | 18.4 % | 7 |
| Con caché | baseline | 9.2 % | 11.7 % | 20.8 % | 209.7 | 211.8 | 20.7 % | 29 |
| Con caché | carga | 36.7 % | 44.4 % | 48.3 % | 213.3 | 218.0 | 21.3 % | 17 |
| Con caché | estrés | 124.5 % | 128.3 % | 138.3 % | 228.4 | 230.9 | 22.6 % | 85 |
| Sin caché | reposo | 0.5 % | 2.2 % | 2.3 % | 187.6 | 188.9 | 18.5 % | 7 |
| Sin caché | baseline | 99.6 % | 108.1 % | 109.5 % | 391.5 | 499.2 | 48.7 % | 411 |
| Sin caché | carga | 105.6 % | 112.7 % | 114.2 % | 486.0 | 592.1 | 57.8 % | 950 |
| Sin caché | estrés | 105.4 % | 112.2 % | 114.8 % | 506.5 | 630.2 | 61.6 % | 1,026 |

### 4.2. MLflow (límite: 100 % de CPU, 1,024 MiB)

| Configuración | Escenario | CPU media | CPU p95 | CPU máx | Memoria media (MiB) | Memoria máx (MiB) | Memoria máx (%) |
|---|---|---:|---:|---:|---:|---:|---:|
| Con caché | reposo | 1.5 % | 2.9 % | 3.1 % | 1,010.8 | 1,011.8 | 98.8 % |
| Con caché | baseline | 1.9 % | 3.5 % | 12.6 % | 1,011.3 | 1,019.5 | 99.5 % |
| Con caché | carga | 1.4 % | 2.9 % | 10.9 % | 1,012.3 | 1,024.2 | 100.0 % |
| Con caché | estrés | 1.6 % | 3.1 % | 11.0 % | 1,012.0 | 1,020.4 | 99.7 % |
| Sin caché | reposo | 1.6 % | 3.0 % | 3.1 % | 1,010.1 | 1,010.9 | 98.7 % |
| Sin caché | baseline | 33.8 % | 55.5 % | 60.7 % | 1,015.0 | 1,024.2 | 100.0 % |
| Sin caché | carga | 23.6 % | 41.9 % | 70.5 % | 1,013.1 | 1,024.2 | 100.0 % |
| Sin caché | estrés | 24.2 % | 45.8 % | 57.1 % | 1,012.3 | 1,024.2 | 100.0 % |

Las series completas están en las gráficas `*_recursos.png` de cada carpeta (sección 9).

## 5. Interpretación

### 5.1. Con caché: la API usa poco más de un núcleo y MLflow casi no trabaja

- La CPU de la API crece con la carga (9 % → 37 % → 125 %) y en estrés llega a 138 % como
  máximo, es decir, 69 % de su límite. La memoria apenas se mueve: de 188 MiB en reposo a
  231 MiB en estrés (23 % del límite).
- La API corre con un solo proceso de uvicorn. Python ejecuta el código de un proceso en un
  núcleo a la vez, con tramos en paralelo cuando numpy o scikit-learn liberan el intérprete. Por
  eso la API no llega al 200 % aunque el p95 se acerque al límite: el segundo CPU asignado se usa
  solo en parte.
- MLflow trabaja únicamente cuando la API recarga un champion (cada 300 s): su CPU media se
  queda entre 1.4 % y 1.9 % en todos los escenarios.

### 5.2. Sin caché: la carga de modelos satura el único proceso de la API

- Desde baseline, la API se queda en ~100–115 % de CPU: un núcleo completo, el máximo que
  aprovecha un solo proceso en esta operación. Cargar el modelo en cada petición es trabajo de
  CPU, y con un núcleo saturado el servicio no pasa de ~3 RPS.
- Los hilos (PIDS) suben de 7 a 1,026 y la memoria de 188 a 630 MiB. Las peticiones en espera
  se acumulan en hilos, y como esta versión no comparte el modelo entre peticiones, es probable
  que varias cargas simultáneas expliquen la memoria. La memoria crece durante toda la
  prueba (ver `sin_cache/estres/estres_recursos.png`); con más tiempo o más usuarios llegaría al
  límite de 1 GiB.
- MLflow sube a 24–34 % de CPU media por las descargas de artefactos. No es el cuello de
  botella en esta medición.

### 5.3. MLflow vive en el límite de memoria, con o sin tráfico

MLflow usa 1,010 MiB de 1,024 MiB (98.7 %) incluso en reposo. La lectura de
`/sys/fs/cgroup/memory.stat` dentro del contenedor muestra ~755 MiB de memoria anónima (del
proceso) y menos de 1 MiB de caché de archivos: el kernel ya vació la caché para no pasar el
límite. No hubo terminaciones por falta de memoria (`oom_kill 0`), pero el servicio no tiene
margen. Es la misma situación que registró `docker stats` el 20 de noviembre (98.6 %), así que
no depende del motor de contenedores.

## 6. Riesgos identificados

1. **Memoria de MLflow al límite.** Cualquier aumento (más versiones, más usuarios de la UI, una
   actualización de MLflow) puede provocar que el kernel lo termine. Afecta las recargas de la
   API y la importación de modelos al arrancar.
2. **Capacidad de la API limitada a un proceso.** Con caché el p95 llega a 410 ms con 100
   usuarios y la API usa poco más de un núcleo. Pasar de ese nivel de tráfico requiere más
   procesos de uvicorn, no más CPU por proceso.
3. **Regresión si se desactiva la caché.** Con `MODEL_CACHE_SECONDS=0` o una imagen anterior al
   PR #27, el servicio cae a ~3 RPS, la latencia llega a decenas de segundos y la memoria crece
   sin control.
4. **Recargas del champion.** Con caché, cada 300 s una petición paga la recarga. En estas
   pruebas no afectó el p95, pero un champion más grande sí podría hacerlo.

## 7. Recomendaciones

1. **Subir el límite de memoria de MLflow** a 1.5 GiB e investigar qué ocupa sus ~755 MiB (ya
   corre con `--workers=1`); vigilar `memory.events` en busca de eventos `oom`.
2. **Mantener la caché activa** como configuración obligatoria del despliegue y documentar que
   `MODEL_CACHE_SECONDS=0` solo sirve para diagnóstico.
3. **Para escalar la API, agregar workers de uvicorn** (por ejemplo `--workers 2`) antes que
   CPU: hoy el segundo CPU asignado se aprovecha solo en parte. Medir de nuevo, porque cada
   worker duplica la memoria de la API (~230 MiB).
4. **Reducir el límite de memoria de la API** a 512 MiB con caché (usa 231 MiB como máximo); el
   límite de 1 GiB solo tendría sentido sin caché.
5. **Alertas**: p95 > 400 ms sostenido, CPU de la API > 150 %, memoria de MLflow > 95 % y
   cualquier evento `oom`.
6. Corregir el docstring de `cached_champion` en `mibici/api.py`: dice que con
   `MODEL_CACHE_SECONDS=0` se carga "como antes", pero el candado por pregunta lo hace distinto.

## 8. Limitaciones

- **Una sola corrida por configuración.** Los valores son indicativos, no un promedio de
  repeticiones.
- **Locust y los contenedores comparten el equipo.** El cliente de carga compite por CPU con la
  API.
- **Podman en WSL2, no Docker Desktop.** Las mediciones del 20 de noviembre (`reports/carga/` y
  `reports/carga_sin_cache/`) se hicieron con Docker y no son comparables en valor absoluto:
  - Con caché, aquí todos los POST tienen un piso de ~45 ms, incluidas las peticiones inválidas
    que responden 422, mientras `GET /health` responde en 2 ms. Con Docker el p50 fue de 7 ms.
    No se determinó la causa; lo más probable es la red de la máquina virtual.
  - Sin caché, Docker atendió 51–97 RPS y Podman ~3 RPS con el mismo código. Lo que coincide en
    ambos entornos es la conclusión: sin caché no se cumplen los límites y con caché sí.
- **CPU de escritorio.** El Core Ultra 9 rinde por núcleo más que una instancia de nube típica;
  la capacidad en AWS debe confirmarse con una prueba en la instancia elegida.
- **Muestreo cada 2 s.** No capta picos más cortos que el intervalo.

## 9. Evidencia

Cada carpeta contiene `resumen.md` y `resumen.json` (Locust y recursos), el reporte HTML de
Locust con sus gráficas y `*_recursos.png` (CPU y memoria en el tiempo). Las series crudas
(`*.csv`) se generan localmente y no se versionan.

| Escenario | Con caché | Sin caché |
|---|---|---|
| Reposo | [con_cache/reposo](con_cache/reposo/reposo_recursos.png) | [sin_cache/reposo](sin_cache/reposo/reposo_recursos.png) |
| Baseline | [con_cache/baseline](con_cache/baseline/resumen.md) | [sin_cache/baseline](sin_cache/baseline/resumen.md) |
| Carga | [con_cache/carga](con_cache/carga/resumen.md) | [sin_cache/carga](sin_cache/carga/resumen.md) |
| Estrés | [con_cache/estres](con_cache/estres/resumen.md) | [sin_cache/estres](sin_cache/estres/resumen.md) |

Reproducción (con la imagen correspondiente levantada con Compose):

```text
python -m mibici.resource_monitor --engine podman --seconds 60 --output reports/recursos/con_cache/reposo
python -m mibici.load_test --scenario estres --stats podman --output reports/recursos/con_cache/estres
```

Con Docker se usa `--engine docker` / `--stats docker`.

## 10. Conclusión

La configuración desplegada (con caché) cumple los límites en los tres escenarios. Con 100
usuarios atiende 211 RPS con p95 de 410 ms, usando 1.25 núcleos de los 2 asignados a la API y
231 MiB de su 1 GiB. El recurso crítico no es la API sino la memoria de MLflow, que opera al
99 % de su límite incluso sin tráfico. Sin caché, la carga del modelo en cada petición satura el
único proceso de la API y el servicio deja de ser utilizable. El dimensionamiento y el costo se
analizan en el [análisis FinOps](../finops/analisis_costos.md).
