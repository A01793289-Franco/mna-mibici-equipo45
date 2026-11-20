# Verificación de Compose con modelos reales

La ejecución documentada en `verification.json` construyó la imagen desde el
`Containerfile`, levantó MLflow y FastAPI con `docker compose up --build -d --wait`,
importó los modelos del Registry y verificó inferencias por HTTP. Los hashes de los
archivos permiten identificar la configuración probada. No se guardan modelos ni bases
de MLflow en Git.

| Modelo | Origen | Resultado de la petición de prueba |
|---|---|---|
| P1 `mibici-p1-demanda`, v1 | Run `da28d047b8384d089de6f74fcd4e175d` | Demanda esperada: `2.6144151108240576` |
| P2 `mibici-p2-riesgo`, v1 | Run `fb52c91b260843a992fe74ecfac7201c` | Clase `1`, `riesgo_sin_bicicletas` |

Ambos modelos proceden del entrenamiento real de la segunda entrega; se exportaron
desde una copia aislada del Registry histórico. La importación reprodujo sus predicciones
y probabilidades con tolerancia `1e-12`. El origen no se alteró ni se reentrenó para esta
comprobación. P2 es el proxy de inventario virtual, con las limitaciones ya documentadas.

- `http-real.json`: 11 controles HTTP correctos después del primer arranque.
- `http-real-restart.json`: los mismos 11 controles después de `down` y `up`.
- `verification.json`: versiones de Docker/Compose, imagen, procedencia, hashes y estados.

Tras recrear los contenedores, P1 y P2 conservaron una versión cada uno y el alias
`champion`. MLflow y API quedaron saludables y `registry-init` terminó con código 0.
La suite completa aprobó 281 pruebas, además de 16 subpruebas. Flake8 y MkDocs estricto
aprobaron; Bandit no encontró problemas de severidad media/alta. El escaneo de secretos
e historial aprobó. `pip-audit` no encontró vulnerabilidades adicionales a las excepciones
ya documentadas en el proyecto.

Esta evidencia valida orquestación e integración; no mide carga ni costo por inferencia.
Los artefactos del job `compose` en GitHub Actions se generan por separado con datos
sintéticos identificados para CI. La [guía de operación](../../references/operacion_compose.md)
contiene los requisitos y comandos para reproducir ambos escenarios.
