# Carga de la API: modelo cargado en cada petición frente a modelo en memoria

Misma API, mismas variables aleatorias y mismos escenarios de Locust
(`python -m mibici.load_test`), medidos sobre Docker Compose con los champion reales de P1 y P2.
Los límites de los contenedores son los de `docker-compose.yml` (API: 2 CPU y 1 GiB; MLflow: 1 CPU y 1 GiB).

- **Sin caché** (`MODEL_CACHE_SECONDS=0`): comportamiento anterior; cada petición consulta a MLflow y
  descarga y carga el modelo. Datos en `reports/carga_sin_cache/`.
- **Con caché** (por defecto, 300 s): el champion se carga una vez y se conserva en memoria.
  Datos en `reports/carga/`.

## Resultados

| Escenario | Usuarios | Modo | Peticiones | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Errores | Memoria de la API al final |
|---|---|---|---|---|---|---|---|---|---|
| baseline (60 s) | 5 | sin caché | 662 | 11.14 | 120 | 320 | 410 | 0 % | 830.6 MiB (81 %) |
| baseline (60 s) | 5 | con caché | 906 | 15.25 | 7 | 19 | 24 | 0 % | n/d por escenario |
| carga (120 s) | 25 | sin caché | 6 152 | 51.79 | 9 | 680 | 3 700 | 0 % | 957.9 MiB (93.5 %) |
| carga (120 s) | 25 | con caché | 9 274 | 78.13 | 8 | 28 | 41 | 0 % | n/d por escenario |
| estrés (120 s) | 100 | sin caché | 11 654 | 97.50 | 390 | 590 | 13 000 | 0 % | 1 009 MiB (98.5 %) |
| estrés (120 s) | 100 | con caché | 18 652 | 156.22 | 380 | 490 | 530 | 0 % | 244.2 MiB (23.8 %) tras los tres escenarios |

El límite acordado para la actividad es p95 ≤ 500 ms y errores ≤ 1 %: sin caché fallan `carga` y `estres`
por latencia; con caché cumplen los tres escenarios.

## Lectura

- El caché reduce el p95 de 320 a 19 ms (baseline) y de 680 a 28 ms (carga), y el p99 del estrés de
  13 s a 0.53 s. El rendimiento sube entre 37 % y 60 %.
- Sin caché la API termina cada escenario cerca del límite de memoria; con caché, tras los tres
  escenarios seguidos, usa 244 MiB.
- En estrés el p95 (490 ms) queda apenas bajo el límite: con 100 usuarios la API está cerca de su
  capacidad con 2 CPU. Es el punto a revisar en el análisis de recursos.
- MLflow permanece en alrededor de 1 GiB de 1 GiB (98.5 %) incluso sin tráfico; el límite de memoria
  de ese servicio es justo.

## Condiciones y limitaciones

- Sin caché, cada escenario arrancó con contenedores recién creados. Con caché, los tres escenarios
  corrieron seguidos sin reiniciar; esta diferencia es conservadora para la comparación.
- En una corrida previa, encadenando escenarios sin reiniciar y sin caché, el servicio se degradó
  hasta responder 503 en cerca del 80 % de las peticiones. Esa corrida no se conserva porque quedó
  mezclada con otras; se incluye como observación, no como medición.
- En `baseline` y `carga` el RPS lo limita el número de usuarios y su tiempo de espera (0.1–0.5 s), no
  la capacidad del servidor. La capacidad se lee en `estres`.
- Locust y los contenedores corrieron en el mismo equipo, así que el cliente de carga compite por CPU.
  Cada configuración se midió una sola vez; los valores son indicativos, no un promedio de varias
  repeticiones.
- La memoria con caché se registró una vez, al terminar los tres escenarios.
