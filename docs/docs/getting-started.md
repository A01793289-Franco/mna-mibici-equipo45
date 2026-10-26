# Primeros pasos

Requiere Python 3.13. Desde la raíz del repositorio, con el entorno activado:

```bash
python -m pip install -r requirements.txt
python -m mibici.dataset          # descarga, limpia y versiona los datos
python -m mibici.features         # construye las variables de P1-P3
python -m mibici.dataset --verify
python -m mibici.features --verify
python -m unittest discover -s tests -v
python -m mibici.train --question all
python -m mibici.predict --question P1 --timestamp 2026-09-15T08:00
```

Con `make` disponible, los mismos pasos son `make data`, `make features`, `make verify`, `make test` y `make train`. `make train` no evalúa septiembre; la prueba final se ejecuta a mano una sola vez, según `references/protocolo_experimento.md`.
