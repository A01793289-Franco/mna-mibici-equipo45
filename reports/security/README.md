# Evidencia de seguridad y organización de pruebas

Esta revisión completa los puntos 3 y 4 de la actividad sobre el trabajo de PyTest y DeepChecks integrado por el equipo. Código ejecutado: `edd2f69bdbb2db74ffbbff3972a8c93c7ab7a051`. Entorno: Python 3.13.15 en Linux, con las versiones de `requirements-validation.txt`.

## Resultados

| Comprobación | Resultado |
|---|---|
| Suite completa, `python -m pytest -v` | 184 pruebas y 12 subtests aprobados |
| Seguridad y privacidad, grupo específico | 49 pruebas aprobadas |
| Archivos actuales e historial de Git | Sin hallazgos de patrones de secretos o archivos privados |
| Bandit, severidad media o alta | 0 hallazgos; 6 avisos bajos por consultas a Git mediante subprocess |
| Auditoría inicial sin exclusiones | 6 entradas en MLflow 3.16.1 y setuptools 80.10.2 |
| Auditoría posterior a actualizar MLflow a 3.17.2 | 3 entradas de setuptools, correspondientes a 2 avisos distintos |
| Auditoría con las dos excepciones documentadas | Código de salida 0 |
| Compatibilidad de modelos históricos | P1, P2 y P3 cargados; 5 predicciones guardadas por modelo reproducidas |

La auditoría sin exclusiones termina con código 1 por los avisos de setuptools. Se mantiene una distinción explícita entre ese resultado y la ejecución con excepciones. DeepChecks requiere la versión anterior a la eliminación de `pkg_resources`; CI instala las dependencias externas solo desde wheels y utiliza pip moderno. Las condiciones y fuentes están en la [guía de verificación](../../docs/docs/verificacion.md).

## Evidencia estructurada

- [Revisión del repositorio e historial](repositorio.json): cobertura, commit y hallazgos sin valores sensibles.
- [Resultados y versiones](resumen.json): auditorías antes y después, pruebas, Bandit y compatibilidad de los modelos.

El control de privacidad confirma que la normalización elimina correo, nombre, identificador de usuario y año de nacimiento. Los tests y modelos de prueba usan datos sintéticos y carpetas temporales.

## Reproducción

Después de instalar `requirements-validation.txt`, desde la raíz:

```text
python -m pytest -v
python -m mibici.security --history --output reports/security/repositorio.json
python -m bandit -c pyproject.toml -r mibici -ll
python -m pip_audit --skip-editable --progress-spinner off --ignore-vuln PYSEC-2026-3447 --ignore-vuln GHSA-xmj3-9gf7-h52w
```

Con Make disponible, `make test` y `make security` ejecutan los mismos controles. La [guía de tests](../../tests/README.md) identifica los archivos de cada grupo y sus fixtures compartidas.
