# Validación de datos con DeepChecks

- Generado: 2026-10-31T21:13:26+00:00
- deepchecks 0.19.1, semilla 42, muestra de drift 100,000 filas por conjunto
- data_version `5ca52ccee062`, feature_version `87c1e6136a5f`
- Resultado de suites bloqueantes: **aprobado**

Las suites de integridad y partición son bloqueantes. El drift es informativo: enero-junio, julio-agosto y septiembre tienen estacionalidad esperada, y month se excluye porque cada partición cubre meses distintos. Comparar distribuciones de septiembre no evalúa modelos ni consume el uso único del conjunto de prueba. MultivariateDrift no se usa: es incompatible con scikit-learn 1.9.

| Conjunto | Suite | Comparación | Bloqueante | Check | Estado | Detalle |
|---|---|---|---|---|---|---|
| p1 | integridad | completo | sí | ExpectedDtypes | aprobado | Columnas y tipos coinciden |
| p1 | integridad | completo | sí | MixedDataTypes | aprobado | 13 columns passed: found 0 columns with negligible types mix, and 13 columns without any types mix |
| p1 | integridad | completo | sí | PercentOfNulls | aprobado | Passed for 9 relevant columns |
| p1 | integridad | completo | sí | MixedNulls | aprobado | Passed for 13 relevant columns |
| p1 | integridad | completo | sí | DataDuplicates | aprobado | Found 0% duplicate data |
| p1 | integridad | completo | sí | DataDuplicates | aprobado | Found 0% duplicate data |
| p1 | integridad | completo | sí | IsSingleValue | aprobado | Passed for 12 relevant columns |
| p1 | integridad | completo | sí | ValueRules | aprobado | 8 reglas sin filas inválidas |
| p1 | particion | train-val | sí | DateTrainTestLeakageOverlap | aprobado | No leaked dates found |
| p1 | drift | train-val | no | FeatureDrift | aprobado | Passed for 8 columns out of 8 columns. Found column "weekday" has the highest categorical drift score: 0.02 Found column "departures_mean_168" has the highest numerical drift score: 0.09 |
| p1 | drift | train-val | no | LabelDrift | aprobado | Label's drift score Kolmogorov-Smirnov is 0.03 |
| p1 | particion | train-test | sí | DateTrainTestLeakageOverlap | aprobado | No leaked dates found |
| p1 | drift | train-test | no | FeatureDrift | aprobado | Passed for 8 columns out of 8 columns. Found column "weekday" has the highest categorical drift score: 0.05 Found column "departures_mean_24" has the highest numerical drift score: 0.04 |
| p1 | drift | train-test | no | LabelDrift | aprobado | Label's drift score Kolmogorov-Smirnov is 0.02 |
| p2 | integridad | completo | sí | ExpectedDtypes | aprobado | Columnas y tipos coinciden |
| p2 | integridad | completo | sí | MixedDataTypes | aprobado | 16 columns passed: found 0 columns with negligible types mix, and 16 columns without any types mix |
| p2 | integridad | completo | sí | PercentOfNulls | aprobado | Passed for 12 relevant columns |
| p2 | integridad | completo | sí | MixedNulls | aprobado | Passed for 16 relevant columns |
| p2 | integridad | completo | sí | DataDuplicates | aprobado | Found 0% duplicate data |
| p2 | integridad | completo | sí | DataDuplicates | aprobado | Found 0% duplicate data |
| p2 | integridad | completo | sí | IsSingleValue | aprobado | Passed for 15 relevant columns |
| p2 | integridad | completo | sí | ValueRules | aprobado | 11 reglas sin filas inválidas |
| p2 | particion | train-val | sí | DateTrainTestLeakageOverlap | aprobado | No leaked dates found |
| p2 | particion | train-val | sí | NewLabelTrainTest | aprobado | Found 0 new labels in test data: [] |
| p2 | drift | train-val | no | FeatureDrift | aprobado | Passed for 11 columns out of 11 columns. Found column "weekday" has the highest categorical drift score: 0.02 Found column "departures_mean_168" has the highest numerical drift score: 0.08 |
| p2 | drift | train-val | no | LabelDrift | aprobado | Label's drift score Cramer's V is 0.06 |
| p2 | particion | train-test | sí | DateTrainTestLeakageOverlap | aprobado | No leaked dates found |
| p2 | particion | train-test | sí | NewLabelTrainTest | aprobado | Found 0 new labels in test data: [] |
| p2 | drift | train-test | no | FeatureDrift | aprobado | Passed for 11 columns out of 11 columns. Found column "weekday" has the highest categorical drift score: 0.06 Found column "virtual_occupancy" has the highest numerical drift score: 0.08 |
| p2 | drift | train-test | no | LabelDrift | aprobado | Label's drift score Cramer's V is 0.1 |
| p3 | integridad | p3_train | sí | ExpectedDtypes | aprobado | Columnas y tipos coinciden |
| p3 | integridad | p3_train | sí | MixedDataTypes | aprobado | 53 columns passed: found 0 columns with negligible types mix, and 53 columns without any types mix |
| p3 | integridad | p3_train | sí | PercentOfNulls | aprobado | Passed for 48 relevant columns |
| p3 | integridad | p3_train | sí | MixedNulls | aprobado | Passed for 53 relevant columns |
| p3 | integridad | p3_train | sí | DataDuplicates | aprobado | Found 0% duplicate data |
| p3 | integridad | p3_train | sí | DataDuplicates | aprobado | Found 0% duplicate data |
| p3 | integridad | p3_train | sí | IsSingleValue | aprobado | Passed for 5 relevant columns |
| p3 | integridad | p3_train | sí | ValueRules | aprobado | 5 reglas sin filas inválidas |
| p3 | integridad | p3_val | sí | ExpectedDtypes | aprobado | Columnas y tipos coinciden |
| p3 | integridad | p3_val | sí | MixedDataTypes | aprobado | 53 columns passed: found 0 columns with negligible types mix, and 53 columns without any types mix |
| p3 | integridad | p3_val | sí | PercentOfNulls | aprobado | Passed for 48 relevant columns |
| p3 | integridad | p3_val | sí | MixedNulls | aprobado | Passed for 53 relevant columns |
| p3 | integridad | p3_val | sí | DataDuplicates | aprobado | Found 0% duplicate data |
| p3 | integridad | p3_val | sí | DataDuplicates | aprobado | Found 0% duplicate data |
| p3 | integridad | p3_val | sí | IsSingleValue | aprobado | Passed for 5 relevant columns |
| p3 | integridad | p3_val | sí | ValueRules | aprobado | 5 reglas sin filas inválidas |
| p3 | integridad | p3_test | sí | ExpectedDtypes | aprobado | Columnas y tipos coinciden |
| p3 | integridad | p3_test | sí | MixedDataTypes | aprobado | 53 columns passed: found 0 columns with negligible types mix, and 53 columns without any types mix |
| p3 | integridad | p3_test | sí | PercentOfNulls | aprobado | Passed for 48 relevant columns |
| p3 | integridad | p3_test | sí | MixedNulls | aprobado | Passed for 53 relevant columns |
| p3 | integridad | p3_test | sí | DataDuplicates | aprobado | Found 0% duplicate data |
| p3 | integridad | p3_test | sí | DataDuplicates | aprobado | Found 0% duplicate data |
| p3 | integridad | p3_test | sí | IsSingleValue | aprobado | Passed for 5 relevant columns |
| p3 | integridad | p3_test | sí | ValueRules | aprobado | 5 reglas sin filas inválidas |
| p3 | drift | train-val | no | FeatureDrift | fallido | Failed for 1 out of 48 columns. Found 1 numeric columns with Kolmogorov-Smirnov above threshold: {'weekend_05': '0.24'} |
| p3 | drift | train-test | no | FeatureDrift | fallido | Failed for 6 out of 48 columns. Found 6 numeric columns with Kolmogorov-Smirnov above threshold: {'weekday_00': '0.2', 'weekday_20': '0.2', 'weekday_21': '0.2', 'weekend_00': '0.3', 'weekend_05': '0.32', 'weekend_23': '0.21'} |
