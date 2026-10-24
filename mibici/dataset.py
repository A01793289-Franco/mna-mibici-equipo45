"""Descarga, limpia y versiona los archivos mensuales de MiBici.

Resuelve los CSV publicados en el portal, normaliza columnas y fechas por bloques, descarta
registros inválidos, duplicados y atributos personales, y escribe un Parquet por mes. El
manifiesto con URL, conteos y hashes SHA-256 define ``data_version``, que liga las variables y
los runs de MLflow con los datos exactos que usaron.
"""

import argparse
import codecs
import csv
from datetime import date, datetime, timezone
import hashlib
from html.parser import HTMLParser
from importlib.metadata import version
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urljoin, urlparse

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from mibici import config as cfg

TRIP_ALIASES = {
    "trip_id": ("viaje_id", "id_viaje", "trip_id"),
    "started_at": ("inicio_del_viaje", "fecha_inicio", "inicio", "started_at"),
    "ended_at": ("fin_del_viaje", "fecha_fin", "fin", "ended_at"),
    "origin_id": ("origen_id", "estacion_origen", "origin_id"),
    "destination_id": ("destino_id", "estacion_destino", "destination_id"),
}
STATION_ALIASES = {
    "station_id": ("id", "estacion_id", "station_id"),
    "name": ("name", "nombre"),
    "latitude": ("latitude", "latitud"),
    "longitude": ("longitude", "longitud"),
    "capacity": ("dpcapacity", "capacidad", "capacity"),
}
TRIP_SCHEMA = pa.schema(
    [
        ("trip_id", pa.int64()),
        ("started_at", pa.timestamp("us", tz=cfg.TIMEZONE)),
        ("ended_at", pa.timestamp("us", tz=cfg.TIMEZONE)),
        ("origin_id", pa.int32()),
        ("destination_id", pa.int32()),
    ]
)


def sha256_file(path):
    """Calcula el hash por bloques, sin cargar el archivo completo."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value):
    """Identifica contenido JSON con un orden independiente del sistema operativo.

    Ordena las llaves antes de serializar: el mismo manifiesto produce la misma versión en
    cualquier máquina.
    """
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def source_hash(path):
    """Identifica código normalizando LF/CRLF para compartir versiones entre sistemas.

    ``read_text`` traduce los saltos de línea, de modo que un archivo con CRLF en Windows tiene
    el mismo hash que con LF en Linux.
    """
    return hashlib.sha256(Path(path).read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def write_json(path, value):
    """Publica un manifiesto completo mediante reemplazo atómico.

    Escribe un archivo temporal y lo renombra al final, para que una interrupción no deje un
    JSON a medias. Fuerza saltos de línea LF para que el archivo sea idéntico en Windows y Linux.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    temporary.replace(path)


def http_session():
    """Crea una sesión identificable con reintentos para fallas transitorias.

    Envía el User-Agent del proyecto y reintenta hasta tres veces ante respuestas 429 y 5xx.
    """
    session = requests.Session()
    session.headers.update(cfg.REQUEST_HEADERS)
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


class CSVLinks(HTMLParser):
    """Extrae enlaces CSV del portal, sin fijar los identificadores de cada mes.

    Acumula en ``links`` las URL absolutas de las etiquetas ``<a>`` que terminan en ``.csv``.
    """

    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        """Guarda el ``href`` de una etiqueta ``<a>`` cuando apunta a un CSV."""
        for name, value in attrs:
            if tag == "a" and name == "href" and value and value.lower().endswith(".csv"):
                self.links.append(urljoin(cfg.DATA_PORTAL_URL, value))


def discover_sources(session, start, end):
    """Resuelve todos los meses completos solicitados; falla si falta alguno.

    Busca ``datos_abiertos_AAAA_MM.csv`` para cada mes de ``[start, end)`` y devuelve mes, URL y
    ruta cruda relativa. Un mes ausente detiene la ingesta en lugar de continuar con un periodo
    incompleto.
    """
    response = session.get(cfg.DATA_PORTAL_URL, timeout=cfg.DOWNLOAD_TIMEOUT)
    response.raise_for_status()
    parser = CSVLinks()
    parser.feed(response.text)
    available = {Path(urlparse(url).path).name: url for url in parser.links}
    sources = []
    for period in pd.period_range(start, end - pd.Timedelta(days=1), freq="M"):
        filename = f"datos_abiertos_{period.year}_{period.month:02d}.csv"
        if filename not in available:
            raise ValueError(f"El portal no publica el mes solicitado: {filename}")
        sources.append(
            {"month": str(period), "url": available[filename], "raw_path": f"raw/{filename}"}
        )
    return sources


def download_file(session, url, path, expected_hash=None, refresh=False):
    """Descarga atómicamente y rechaza cambios respecto de la versión registrada.

    Si el archivo existe y no se pide ``refresh``, solo comprueba su hash. Una descarga nueva se
    escribe en un ``.part`` y se rechaza si no coincide con ``expected_hash``, para no mezclar
    una fuente actualizada con la versión anterior.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not refresh:
        if expected_hash and sha256_file(path) != expected_hash:
            raise ValueError(f"Hash distinto al manifiesto: {path.name}")
        return
    temporary = path.with_suffix(path.suffix + ".part")
    try:
        with session.get(url, stream=True, timeout=cfg.DOWNLOAD_TIMEOUT) as response:
            response.raise_for_status()
            with temporary.open("wb") as output:
                for block in response.iter_content(1024 * 1024):
                    output.write(block)
        if expected_hash and not refresh and sha256_file(temporary) != expected_hash:
            raise ValueError(f"La fuente cambió; no se puede reconstruir {path.name}")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def csv_format(path):
    """Detecta UTF-8, Windows-1252 o Latin-1 y el delimitador de cada archivo.

    Prueba las codificaciones en ese orden leyendo el archivo completo y aplica ``csv.Sniffer``
    a los primeros 8 KB. Devuelve ``(codificación, separador)``.
    """
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with codecs.open(path, "r", encoding=encoding) as stream:
                while stream.read(1024 * 1024):
                    pass
            break
        except UnicodeError:
            continue
    with Path(path).open(encoding=encoding, newline="") as stream:
        sample = stream.read(8192)
    return encoding, csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter


def column_mapping(columns, aliases):
    """Normaliza acentos, espacios y variantes de las columnas necesarias.

    Devuelve ``{columna original: nombre estándar}`` según ``aliases``. Si falta una columna
    requerida, falla mostrando las cabeceras recibidas.
    """

    def normalize(text):
        """Quita acentos, pasa a minúsculas y reemplaza separadores por ``_``."""
        text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
        return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")

    normalized = {normalize(name): name for name in columns}
    mapping = {}
    for target, candidates in aliases.items():
        matches = [normalized[name] for name in candidates if name in normalized]
        if not matches:
            raise ValueError(f"Falta la columna requerida {target}. Cabeceras: {list(columns)}")
        mapping[matches[0]] = target
    return mapping


def local_dates(values):
    """Interpreta fechas locales: ISO o día/mes/año, y conserva zona horaria explícita.

    Las fechas ISO se leen como año-mes-día y las demás con el día primero; ambas se localizan
    en ``America/Mexico_City``. Una fecha con desplazamiento se convierte a esa zona. Las horas
    ambiguas o inexistentes por cambio de horario quedan como ``NaT``.
    """
    values = values.str.strip()
    iso = values.str.match(r"^\d{4}-\d{2}-\d{2}", na=False)
    aware = values.str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", case=False, na=False)
    parsed = pd.to_datetime(values.where(iso & ~aware), format="ISO8601", errors="coerce")
    other = pd.to_datetime(
        values.where(~iso & ~aware), format="mixed", dayfirst=True, errors="coerce"
    )
    local = parsed.fillna(other).dt.tz_localize(cfg.TIMEZONE, ambiguous="NaT", nonexistent="NaT")
    utc = pd.to_datetime(values.where(aware), format="mixed", utc=True, errors="coerce")
    return local.fillna(utc.dt.tz_convert(cfg.TIMEZONE)).dt.as_unit("us")


def normalize_trips(frame, start, end, seen):
    """Conserva viajes válidos únicos; elimina atributos personales antes de escribir.

    Selecciona solo las cinco columnas del esquema y descarta IDs no enteros o no positivos,
    fechas inválidas, finales no posteriores al inicio, inicios fuera de ``[start, end)`` e IDs
    ya vistos. Actualiza ``seen`` y devuelve la tabla limpia con el conteo de cada descarte.
    """
    frame = frame.rename(columns=column_mapping(frame.columns, TRIP_ALIASES))
    frame = frame[list(TRIP_ALIASES)].copy()
    for name in ("trip_id", "origin_id", "destination_id"):
        numbers = pd.to_numeric(frame[name], errors="coerce")
        maximum = 2**63 - 1 if name == "trip_id" else 2**31 - 1
        frame[name] = numbers.where((numbers > 0) & (numbers <= maximum) & (numbers % 1 == 0))
    for name in ("started_at", "ended_at"):
        frame[name] = local_dates(frame[name])
    valid = frame.notna().all(axis=1) & (frame.ended_at > frame.started_at)
    invalid = int((~valid).sum())
    frame = frame[valid].copy()
    inside = (frame.started_at >= start) & (frame.started_at < end)
    outside = int((~inside).sum())
    frame = frame[inside].copy()
    duplicate = frame.trip_id.duplicated() | frame.trip_id.isin(seen)
    duplicates = int(duplicate.sum())
    frame = frame[~duplicate].copy()
    for name in ("trip_id", "origin_id", "destination_id"):
        frame[name] = frame[name].astype("int64" if name == "trip_id" else "int32")
    seen.update(frame.trip_id.tolist())
    return frame, {"invalid": invalid, "outside_period": outside, "duplicates": duplicates}


def clean_month(source, data_dir, seen):
    """Limpia por bloques y escribe un Parquet mensual con esquema fijo.

    Lee solo las columnas necesarias en bloques de ``CHUNK_ROWS`` y renombra el temporal al
    terminar. Devuelve la entrada del manifiesto (formato, hashes y conteos) y las estaciones
    observadas como origen o destino.
    """
    raw = data_dir / source["raw_path"]
    encoding, separator = csv_format(raw)
    header = pd.read_csv(raw, encoding=encoding, sep=separator, nrows=0)
    mapping = column_mapping(header.columns, TRIP_ALIASES)
    target = cfg.data_path(cfg.TRIPS_DIR, data_dir) / f"{source['month']}.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    period = pd.Period(source["month"], freq="M")
    start = period.start_time.tz_localize(cfg.TIMEZONE)
    end = (period + 1).start_time.tz_localize(cfg.TIMEZONE)
    counts = {"raw_rows": 0, "clean_rows": 0, "invalid": 0, "outside_period": 0, "duplicates": 0}
    stations = set()
    try:
        with pq.ParquetWriter(temporary, TRIP_SCHEMA, compression="snappy") as writer:
            for chunk in pd.read_csv(
                raw,
                encoding=encoding,
                sep=separator,
                usecols=list(mapping),
                dtype="string",
                chunksize=cfg.CHUNK_ROWS,
            ):
                counts["raw_rows"] += len(chunk)
                clean, discarded = normalize_trips(chunk, start, end, seen)
                counts["clean_rows"] += len(clean)
                for key, count in discarded.items():
                    counts[key] += count
                stations.update(clean.origin_id.tolist())
                stations.update(clean.destination_id.tolist())
                writer.write_table(
                    pa.Table.from_pandas(clean, schema=TRIP_SCHEMA, preserve_index=False)
                )
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        **source,
        "raw_sha256": sha256_file(raw),
        "encoding": encoding,
        "separator": separator,
        "clean_path": target.relative_to(data_dir).as_posix(),
        "clean_sha256": sha256_file(target),
        **counts,
    }, stations


def clean_stations(raw, target):
    """Normaliza catálogo y descarta capacidades/coordenadas inválidas; detecta IDs ambiguos.

    Conserva ID, nombre, coordenadas y capacidad entera positiva; un ID repetido con metadatos
    distintos detiene la ingesta. Devuelve el catálogo limpio y sus conteos para el manifiesto.
    """
    encoding, separator = csv_format(raw)
    frame = pd.read_csv(raw, encoding=encoding, sep=separator, dtype="string")
    raw_rows = len(frame)
    frame = frame.rename(columns=column_mapping(frame.columns, STATION_ALIASES))[
        list(STATION_ALIASES)
    ]
    for name in ("station_id", "latitude", "longitude", "capacity"):
        frame[name] = pd.to_numeric(frame[name], errors="coerce")
    valid = (
        (frame.station_id > 0)
        & (frame.station_id % 1 == 0)
        & (frame.capacity > 0)
        & (frame.capacity % 1 == 0)
    )
    valid &= frame.latitude.between(-90, 90) & frame.longitude.between(-180, 180)
    frame = frame[valid.fillna(False)].drop_duplicates().copy()
    if frame.station_id.duplicated().any():
        raise ValueError("El catálogo contiene un ID con metadatos contradictorios")
    frame[["station_id", "capacity"]] = frame[["station_id", "capacity"]].astype("int32")
    frame["name"] = frame.name.fillna(frame.station_id.astype(str))
    frame = frame.sort_values("station_id").reset_index(drop=True)
    if frame.empty:
        raise ValueError("El catálogo no contiene estaciones válidas")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    frame.to_parquet(temporary, index=False, compression="snappy")
    temporary.replace(target)
    return frame, {
        "raw_rows": raw_rows,
        "clean_rows": len(frame),
        "discarded": raw_rows - len(frame),
        "encoding": encoding,
    }


def verify_manifest(manifest, data_dir):
    """Comprueba todos los archivos crudos y limpios antes de reutilizar la versión.

    Falla si un archivo falta o cambió su SHA-256, o si ``data_version`` no corresponde al
    contenido del manifiesto sin ``created_at``.
    """
    for item in [*manifest["trips"], manifest["stations"]]:
        for kind in ("raw", "clean"):
            path = Path(data_dir) / item[f"{kind}_path"]
            if not path.is_file() or sha256_file(path) != item[f"{kind}_sha256"]:
                raise ValueError(f"Archivo ausente o modificado: {path}")
    payload = {
        key: value for key, value in manifest.items() if key not in ("data_version", "created_at")
    }
    if canonical_hash(payload) != manifest["data_version"]:
        raise ValueError("El manifiesto no coincide con su versión")


def ingest(
    start=cfg.START_DATE,
    end=cfg.END_DATE_EXCLUSIVE,
    data_dir=cfg.DATA_DIR,
    manifest_path=cfg.MANIFEST_PATH,
    refresh=False,
):
    """Reconstruye meses completos y publica una versión verificable de datos sin muestras personales.

    Con el mismo rango reutiliza URL y hashes del manifiesto previo; con otro rango o con
    ``refresh`` los busca en el portal. Conserva ``created_at`` si la versión no cambió, verifica
    el resultado antes de escribirlo y devuelve el manifiesto.
    """
    if start.day != 1 or end.day != 1 or start >= end:
        raise ValueError("Usa meses completos: fechas inicial y final en día 1, fin excluido")
    data_dir, manifest_path = Path(data_dir), Path(manifest_path)
    previous = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    )
    same_range = (
        previous.get("start") == start.isoformat()
        and previous.get("end_exclusive") == end.isoformat()
    )
    session = http_session()
    if same_range and not refresh:
        sources = [
            {key: item[key] for key in ("month", "url", "raw_path")} for item in previous["trips"]
        ]
    else:
        sources = discover_sources(session, start, end)
    expected = {
        item["raw_path"]: item["raw_sha256"]
        for item in [*previous.get("trips", []), previous.get("stations", {})]
        if "raw_path" in item
    }
    catalog_url = previous["stations"]["url"] if previous and not refresh else cfg.STATIONS_URL
    catalog_raw = data_dir / "raw" / Path(urlparse(catalog_url).path).name
    download_file(
        session,
        catalog_url,
        catalog_raw,
        expected.get(catalog_raw.relative_to(data_dir).as_posix()),
        refresh,
    )
    station_path = cfg.data_path(cfg.STATIONS_FILE, data_dir)
    catalog, station_counts = clean_stations(catalog_raw, station_path)
    seen, observed, files = set(), set(), []
    for source in sources:
        print(f"Ingesta {source['month']}...", flush=True)
        download_file(
            session,
            source["url"],
            data_dir / source["raw_path"],
            expected.get(source["raw_path"]),
            refresh,
        )
        item, stations = clean_month(source, data_dir, seen)
        files.append(item)
        observed.update(stations)
        print(f"  {item['clean_rows']:,} viajes válidos", flush=True)
    payload = {
        "schema_version": cfg.DATA_SCHEMA_VERSION,
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "timezone": cfg.TIMEZONE,
        "normalizer_sha256": source_hash(__file__),
        "config_sha256": source_hash(cfg.__file__),
        "packages": {name: version(name) for name in ("pandas", "pyarrow")},
        "trips": files,
        "stations": {
            "url": catalog_url,
            "raw_path": catalog_raw.relative_to(data_dir).as_posix(),
            "raw_sha256": sha256_file(catalog_raw),
            "clean_path": station_path.relative_to(data_dir).as_posix(),
            "clean_sha256": sha256_file(station_path),
            **station_counts,
        },
        "summary": {
            "months": len(files),
            "raw_rows": sum(item["raw_rows"] for item in files),
            "clean_trips": sum(item["clean_rows"] for item in files),
            "observed_stations": len(observed),
            "catalog_stations": len(catalog),
            "stations_outside_catalog": sorted(observed - set(catalog.station_id)),
        },
    }
    manifest = {**payload, "data_version": canonical_hash(payload)}
    manifest["created_at"] = (
        previous.get("created_at")
        if previous.get("data_version") == manifest["data_version"]
        else datetime.now(timezone.utc).isoformat()
    )
    verify_manifest(manifest, data_dir)
    write_json(manifest_path, manifest)
    session.close()
    print(json.dumps(manifest["summary"], ensure_ascii=False, indent=2), flush=True)
    print(f"Versión de datos: {manifest['data_version']}", flush=True)
    return manifest


def main():
    """Expone ingesta, actualización explícita y verificación desde la terminal."""
    parser = argparse.ArgumentParser(description="Descarga, limpia y versiona los archivos mensuales de MiBici.")
    parser.add_argument(
        "--start",
        type=date.fromisoformat,
        default=cfg.START_DATE,
        help="Inicio incluido YYYY-MM-01",
    )
    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        default=cfg.END_DATE_EXCLUSIVE,
        help="Fin excluido YYYY-MM-01",
    )
    parser.add_argument(
        "--data-dir", type=Path, default=cfg.DATA_DIR, help="Carpeta local para datos fuera de Git"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Aceptar una actualización de fuentes y generar otra versión",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verificar hashes de la versión registrada, sin descargar",
    )
    args = parser.parse_args()
    if args.verify:
        verify_manifest(json.loads(cfg.MANIFEST_PATH.read_text(encoding="utf-8")), args.data_dir)
        print("Versión y archivos verificados.")
    else:
        ingest(args.start, args.end, args.data_dir, refresh=args.refresh)


if __name__ == "__main__":
    main()
