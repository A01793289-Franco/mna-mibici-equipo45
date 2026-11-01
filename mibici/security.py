import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

from mibici import config as cfg

TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".toml",
    ".cfg",
    ".yaml",
    ".yml",
    ".json",
    ".ipynb",
    ".example",
    "",
}
SECRET_PATTERNS = {
    "llave privada": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "llave de AWS": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "token de GitHub": re.compile(r"\b(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{30,}|github_pat_\w{40,}"),
    "credencial asignada": re.compile(
        r"(?i)\b(?:password|passwd|secret|api_?key|access_?token)\b\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"
    ),
    "URL con usuario y contraseña": re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@"),
}
PRIVATE_SUFFIXES = {
    ".csv",
    ".parquet",
    ".feather",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pkl",
    ".pickle",
    ".joblib",
    ".skops",
    ".onnx",
    ".h5",
    ".keras",
    ".pt",
    ".pth",
    ".pem",
    ".key",
}
MAX_TEXT_BYTES = 5_000_000


def git(root, *args, input=None):
    return subprocess.run(
        ["git", *args], cwd=root, input=input, capture_output=True, check=True
    ).stdout


def private_path(name):
    path = PurePosixPath(name)
    if path.name == ".gitkeep" or path.name == ".env.example":
        return False
    return (
        path.name == ".env"
        or path.name.startswith(".env.")
        or path.suffix.lower() in PRIVATE_SUFFIXES
        or path.name.startswith("mlflow.db-")
        or any(p in {"mlruns", "mlartifacts", ".venv"} for p in path.parts)
        or name.startswith(("data/", "models/"))
    )


def inspect_text(data, name, scope):
    text = data.decode("utf-8", errors="replace")
    return [
        {"archivo": name, "origen": scope, "problema": kind}
        for kind, pattern in SECRET_PATTERNS.items()
        if pattern.search(text)
    ]


def scan_repository(root=cfg.ROOT_DIR, history=False):
    root = Path(root)
    findings = []
    scanned = {"actuales": 0, "historicos": 0, "textos_grandes_omitidos": 0}
    names = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    for name in filter(None, names.decode("utf-8").split("\0")):
        path = root / name
        if private_path(name):
            findings.append({"archivo": name, "origen": "actual", "problema": "archivo privado"})
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if path.stat().st_size > MAX_TEXT_BYTES:
            scanned["textos_grandes_omitidos"] += 1
            continue
        findings.extend(inspect_text(path.read_bytes(), name, "actual"))
        scanned["actuales"] += 1
    if history:
        objects = [
            row.split(" ", 1)
            for row in git(root, "rev-list", "--objects", "--all").decode("utf-8").splitlines()
            if " " in row
        ]
        ids = "".join(f"{oid}\n" for oid, _ in objects).encode()
        metadata = git(root, "cat-file", "--batch-check", input=ids).decode().splitlines()
        for (oid, name), description in zip(objects, metadata, strict=True):
            _, kind, size = description.split()
            if kind != "blob":
                continue
            if private_path(name):
                findings.append(
                    {"archivo": name, "origen": "historial", "problema": "archivo privado"}
                )
            if PurePosixPath(name).suffix.lower() not in TEXT_SUFFIXES:
                continue
            if int(size) > MAX_TEXT_BYTES:
                scanned["textos_grandes_omitidos"] += 1
                continue
            findings.extend(inspect_text(git(root, "cat-file", "blob", oid), name, "historial"))
            scanned["historicos"] += 1
    unique = {tuple(sorted(item.items())): item for item in findings}
    return {
        "commit": git(root, "rev-parse", "HEAD").decode().strip(),
        "historial_incluido": history,
        "archivos_revisados": scanned,
        "aprobado": not unique,
        "hallazgos": list(unique.values()),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Revisa secretos y archivos privados en Git.")
    parser.add_argument("--history", action="store_true", help="Incluye el historial disponible")
    parser.add_argument(
        "--output", type=Path, help="Guarda el resultado JSON sin valores sensibles"
    )
    args = parser.parse_args(argv)
    result = scan_repository(history=args.history)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["aprobado"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
