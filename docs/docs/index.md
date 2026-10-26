# MiBici | Equipo 45

El proyecto estudia tres preguntas sobre las estaciones de bicicleta pública de Guadalajara.

| Pregunta | Resultado | Uso previsto |
|---|---|---|
| P1 | Demanda de viajes durante la siguiente hora | Planeación operativa |
| P2 | Riesgo de falta de bicicletas o anclajes en un inventario virtual | Estudio del rebalanceo |
| P3 | Grupos de estaciones por su perfil horario | Comparación de patrones |

Los modelos se entrenan con enero-junio de 2026 y se seleccionan con julio-agosto. Septiembre ya se utilizó en la primera entrega; las nuevas cifras de ese mes se presentan como evaluación retrospectiva.

## Guías

- [Reproducir el proyecto](getting-started.md): instalación, ingesta y MLflow Project.
- [API de predicción](api.md): consulta local del modelo elegido de P1 o P2.
- [Pruebas y CI](verificacion.md): comprobaciones locales y automáticas.

## Código y decisiones

- [README](https://github.com/A01793289-Franco/mna-mibici-equipo45/blob/main/README.md).
- [Propuesta y preguntas](https://github.com/A01793289-Franco/mna-mibici-equipo45/blob/main/references/propuesta.md).
- [Arquitectura](https://github.com/A01793289-Franco/mna-mibici-equipo45/blob/main/references/arquitectura.md).
- [Resultados históricos y análisis](https://github.com/A01793289-Franco/mna-mibici-equipo45/blob/main/reports/resultados_mlflow.md).
- [MLflow Project y parámetros](https://github.com/A01793289-Franco/mna-mibici-equipo45/blob/main/references/mlflow_project.md).
- [Ingesta y variables](https://github.com/A01793289-Franco/mna-mibici-equipo45/blob/main/references/ingesta_features.md).
- [Tracking y Registry](https://github.com/A01793289-Franco/mna-mibici-equipo45/blob/main/references/integracion_registry.md).
- [Resultados de la segunda entrega](https://github.com/A01793289-Franco/mna-mibici-equipo45/blob/main/reports/resultados_mlflow_entrega2.md).

## Límites

P2 utiliza un inventario simulado; no demuestra disponibilidad real. La API es una demostración local que consume tablas de variables ya construidas. No calcula predictores de horas futuras ni constituye un servicio operativo del sistema MiBici. P3 se consulta mediante el módulo de predicción de perfiles.
