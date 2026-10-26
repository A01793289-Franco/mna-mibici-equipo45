# Documentación del proyecto

Desde la raíz del repositorio y con las dependencias instaladas:

```text
python -m mkdocs build --strict -f docs/mkdocs.yml
python -m mkdocs serve -f docs/mkdocs.yml -a 127.0.0.1:8001
```

El primer comando construye el sitio en `docs/site`, que está excluido de Git. El segundo permite revisarlo en http://127.0.0.1:8001. Son los mismos comandos en Linux, macOS, PowerShell y CMD.

Los archivos editables están en `docs/docs/`. La documentación enlaza al README y las guías de `main`; no publica el sitio ni modifica GitHub Pages.
