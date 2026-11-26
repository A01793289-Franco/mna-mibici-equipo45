# Evidencia de validación funcional mediante CI/CD

**Proyecto:** MiBici  
**Equipo:** 45  
**Actividad:** Entrega final del proyecto integrador  
**Fecha:** 25 de noviembre de 2026 (hora de México)

## 1. Objetivo

Complementar la consolidación del repositorio y la validación del Model Registry mediante evidencias de ejecución automatizada en GitHub Actions.

## 2. Identificación de la ejecución

| Elemento | Valor |
|---|---|
| Workflow | CI |
| Ejecución | 11 |
| Run ID | 45745713969 |
| Commit | 1238169 |
| Rama | docs/final-repository-registry-validation |
| Resultado | Success |
| Duración total | 11 minutos y 9 segundos |
| Artefactos generados | 2 |

[Evidencia original de GitHub Actions](https://github.com/IsaiPerezA01797871/mna-mibici-equipo45/actions/runs/45745713969)

## 3. Resultados del pipeline

| Proceso | Duración | Resultado |
|---|---|---|
| Python 3.13 / Ubuntu | 3 min 39 s | Aprobado |
| Python 3.13 / Windows | 8 min 41 s | Aprobado |
| Seguridad / dependencias y código | 1 min 36 s | Aprobado |
| Imagen y despliegue de prueba / Compose | 2 min 15 s | Aprobado |

Los cuatro procesos finalizaron exitosamente.

La construcción de la imagen Docker se completó en 23 segundos, con un aprovechamiento de caché del 38 %.

## 4. Estado de los servicios

| Servicio | Estado | Resultado |
|---|---|---|
| FastAPI | Running / Healthy | Correcto |
| MLflow | Running / Healthy | Correcto |
| Registry-init | Exited (0) | Inicialización exitosa |

El servicio Registry-init finaliza después de completar su proceso de inicialización.

## 5. Verificación de la API

| Comprobación | Despliegue inicial | Después del reinicio |
|---|---|---|
| GET /health | HTTP 200 | HTTP 200 |
| GET /openapi.json | HTTP 200 | HTTP 200 |
| POST /predict/p1 | HTTP 200 | HTTP 200 |
| POST /predict/p2 | HTTP 200 | HTTP 200 |
| Siete casos de entradas inválidas | HTTP 422 | HTTP 422 |

Resultados:

- Despliegue inicial: 11 de 11 comprobaciones aprobadas.
- Después de recrear los servicios: 11 de 11 comprobaciones aprobadas.
- Total: 22 de 22 comprobaciones exitosas.

El código HTTP 422 corresponde al comportamiento esperado ante entradas inválidas.

## 6. Integración con el Model Registry

Las respuestas de la API identifican las siguientes referencias de modelos:

- models:/mibici-p1-demanda@champion
- models:/mibici-p2-riesgo@champion

### 6.1 Predicción de P1

| Elemento | Resultado |
|---|---|
| Modelo | mibici-p1-demanda |
| Alias | champion |
| Demanda esperada | 4.0 |
| Respuesta HTTP | 200 |

### 6.2 Predicción de P2

| Elemento | Resultado |
|---|---|
| Modelo | mibici-p2-riesgo |
| Alias | champion |
| Clase | 1 |
| Clasificación | riesgo_sin_bicicletas |
| Probabilidad normal | 0.0 |
| Probabilidad de riesgo sin bicicletas | 1.0 |
| Probabilidad de riesgo sin anclajes | 0.0 |
| Respuesta HTTP | 200 |

Las predicciones se conservaron después de recrear los servicios.

Los resultados corresponden exclusivamente a modelos sintéticos utilizados en el entorno de CI.

## 7. Evidencias de ejecución

El artefacto compose-45745713969-1 contiene los siguientes archivos:

| Archivo | Contenido |
|---|---|
| http.json | Resultados HTTP del despliegue inicial. |
| http-restart.json | Resultados HTTP después de recrear los servicios. |
| services.json | Estado de los contenedores. |
| logs.txt | Registros de ejecución de los servicios. |

[Artefacto original de GitHub Actions](https://github.com/IsaiPerezA01797871/mna-mibici-equipo45/actions/runs/45745713969/artifacts/15083603509)

Los artefactos de Compose tienen una retención configurada de 14 días. Se recomienda conservar una copia de las evidencias relevantes en el repositorio.

## 8. Advertencias y limitaciones

La ejecución presentó una advertencia relacionada con la transición de Node.js 20 a Node.js 24 en determinadas acciones de GitHub.

La advertencia no impidió la finalización exitosa del pipeline. Se recomienda revisar las dependencias de las acciones como parte del mantenimiento futuro.

La validación funcional utiliza datos y modelos sintéticos, por lo que:

- No representa una evaluación del desempeño predictivo real de MiBici.
- No confirma las versiones vigentes del Registry productivo.
- No sustituye la validación de los modelos entrenados con datos reales.
- No demuestra la recuperación funcional de P3 mediante la API.

La ejecución no modifica los aliases del Registry productivo.

## 9. Conclusión

La ejecución exitosa de GitHub Actions proporciona evidencia funcional de la integración del código, las pruebas automatizadas, la seguridad, la construcción de contenedores y el despliegue mediante Docker Compose.

Las 22 comprobaciones HTTP exitosas respaldan la operación de la API, el consumo de modelos P1 y P2 mediante el alias champion y la continuidad funcional después de recrear los servicios en un entorno controlado.

Estos resultados complementan la consolidación del repositorio y la validación documental del Model Registry.

La confirmación de las versiones y aliases del Registry productivo permanece pendiente.

## 10. Documentos relacionados

- [Consolidación del repositorio](consolidacion_repositorio.md).
- [Validación del Model Registry](validacion_registry.md).
- [Configuración del pipeline CI](../../.github/workflows/ci.yml).
