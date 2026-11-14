# Revisión de la actividad de drift y comparación A/B

Fecha de revisión: 14 de noviembre de 2026. Equipo 45.

## Comprobación de los seis pasos

| Paso de la actividad | Evidencia comprobada | Resultado |
|---|---|---|
| 1. Referencia y periodo posterior | `README.md` (monitoreo), `reports/evidently/resumen.json`; enero-junio de referencia y septiembre de evaluación; julio-agosto como periodo intermedio. | Completo: fechas, granularidad, horizonte y conteos documentados. |
| 2. Drift y calidad con Evidently | `mibici/monitoring.py`, HTML P1/P2, capturas y `drift_reproduccion.json`. | Completo: se reprodujeron las cuatro comparaciones, con los mismos valores y tolerancia 1e-12. |
| 3. Interpretación | `reports/evidently/interpretacion_drift.md` y PDF. | Completo: station_id, medias históricas, calidad, alcance del indicador global y límites causales. |
| 4. Alternativa registrada | `mibici/project.py`, `train_window=train_val`; Registry `mibici-p1-demanda`, versiones A=1/B=2 de la reproducción. | Completo: modelos reales entrenados con el código existente; A enero-junio y B enero-agosto. |
| 5. A/B con evaluación común | `mibici/abtest.py`, `resultados.json`, `resultados.md`, `comparacion.png` y protocolo. | Completo: 338,690 filas idénticas; cuatro métricas, segmentos y bootstrap pareado. |
| 6. Reporte y Continuous Training | `reports/TC5061_Drift_ABTest_Equipo45.pdf`. | Completo: portada, cuatro páginas de contenido y dos anexos; fuente equivalente a Arial 11 e interlineado 1.15 en el cuerpo; gráficas, tabla, recomendación y enlaces. |

La actividad permite trabajar con al menos un modelo. P1 cubre el entrenamiento alternativo y la comparación; se conserva además el monitoreo P2 del equipo. La entrega se integra al mismo repositorio y no reemplaza la API, el Containerfile ni las entregas anteriores.

## Hallazgos resueltos

- Se añadió un comparador ejecutable que recupera ambas versiones del mismo Registry. Se resolvió la ausencia del paso 5 con una evaluación real, no con una tabla redactada a mano.
- Los alias se resuelven una vez y la inferencia carga las URI numéricas; firmas, linaje, versiones de datos, cortes temporales y claves de evaluación se validan antes de comparar.
- Se distinguen el error absoluto global, el relativo y el desempeño de las 58 estaciones nuevas respecto de A. En estas últimas B conserva WAPE 101.23 %, aunque mejora el MAE.
- Se retiraron afirmaciones causales no demostradas sobre el aumento de demanda y se actualizó la interpretación con el desglose ya ejecutado.
- Se explicita que septiembre fue observado en entregas anteriores: A/B offline retrospectivo, sin aleatorización de tráfico ni pretensión de prueba final inédita.
- La recomendación es B por las cuatro condiciones del protocolo; no se modificaron los alias del Registry ni se publicó un cambio automático del servicio.
- Se verificaron las aportaciones reales de los cuatro integrantes mediante los PR #20, #21, #22, #23 y el commit A/B 17eb729, con su detalle en README y PDF.

## Reproducción real

El entrenamiento de A/B se realizó desde un clon limpio de `main` en `61f237f05e5ddddd8101460a6b8e7524f8cf8c21`, reutilizando los datos locales verificados por sus manifiestos. No se emplea una base privada de otro integrante: se generó un Registry aislado con el entrenamiento del proyecto.

- A, versión 1: run `a9284a97452a4a2383b1ca148d9a15c7`.
- B, versión 2: run `ad655fdb19c042a190b794e084684c8c`.
- Comparación: run `7a429366dfcd415e80e0a167217deebe`, código limpio `17eb7296b0c04ba7ad62e363b46d82506d2fdb02`.
- Evaluación: septiembre, 338,690 filas y 471 estaciones; hash `7728e0f935f0a27ca4405da1836e59694c5ee9655bf250af847352d3ee7bd757`.
- B: MAE 0.857719 frente a 0.862040; mejora relativa 0.5013 %. IC95 % de la diferencia A-B: [0.002236, 0.006238].
- Alias conservados: `champion`=1 y `challenger`=2.

Los resultados exactos, versiones de paquetes, manifiestos y métricas completas están en `resultados.json`. El protocolo describe las decisiones y su limitación retrospectiva. Los datos, la base del Registry y los modelos permanecen fuera de Git.

## Verificaciones de calidad

| Control | Resultado local |
|---|---|
| `python -m pytest -q` | 259 pruebas y 16 subpruebas aprobadas; 243 avisos de dependencias. |
| `python -m flake8 mibici tests` | Aprobado. |
| `python -m mkdocs build --strict -f docs/mkdocs.yml` | Aprobado. |
| `python -m mibici.security --history` | Aprobado, sin secretos ni archivos privados detectados. |
| `python -m bandit -c pyproject.toml -r mibici -ll` | Aprobado: cero hallazgos medios/altos; seis bajos existentes. |
| `python -m pip_audit` con las excepciones de CI | Aprobado; tres avisos cubiertos por las excepciones documentadas de setuptools/DeepChecks. |
| Reportes Evidently | Cuatro comparaciones reproducidas, sin discrepancias por encima de 1e-12. |
| Documento PDF | Siete páginas renderizadas y revisadas visualmente; cuatro páginas de contenido, dos anexos y portada. |

Las pruebas nuevas validan reproducibilidad del bootstrap, particiones temporales, duplicados, predicciones inválidas, segmentación, firmas y versiones del Registry sin mover alias. Los datos sintéticos se usan solo en tests; el reporte A/B utiliza los dos HGB reales del proyecto.

## Revisión contra la rúbrica

- **Evidently (30 %):** referencia/actual inequívocos, distancias por variable, calidad y gráficas reales.
- **Interpretación (20 %):** variables afectadas y efectos potenciales/medidos, sin confundir cambio de distribución con degradación o causalidad.
- **A/B (30 %):** mismas filas, versiones registradas, linaje, métricas, segmentos e incertidumbre temporal; límites declarados.
- **Continuous Training (10 %):** recomendación B con mejora pequeña; política mensual, revisión antes de entrenar, nueva ventana temporal y reversión.
- **Claridad y colaboración (10 %):** formato solicitado, referencias y evidencia individual de los cuatro integrantes. El historial acredita aportaciones distintas; no se presupone una calificación individual idéntica.

**Resultado de la revisión:** los seis pasos y los elementos del entregable están cubiertos. Esta comprobación no sustituye la evaluación del profesor.
