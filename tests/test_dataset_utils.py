"""Pruebas PyTest de utilidades de ingesta: columnas, formato CSV, hashes y rutas."""

from pathlib import Path

import pytest

from mibici import config as cfg
from mibici.dataset import TRIP_ALIASES, canonical_hash, column_mapping, csv_format

TRIP_HEADERS = ["Viaje Id", "Inicio del viaje", "Fin del viaje", "Origen Id", "Destino Id"]


# ---------------------------------------------------------------------------
# column_mapping: procesamiento de datos
# ---------------------------------------------------------------------------
def test_column_mapping_translates_published_headers():
    mapping = column_mapping(TRIP_HEADERS, TRIP_ALIASES)
    assert mapping == {
        "Viaje Id": "trip_id",
        "Inicio del viaje": "started_at",
        "Fin del viaje": "ended_at",
        "Origen Id": "origin_id",
        "Destino Id": "destination_id",
    }


def test_column_mapping_ignores_accents_case_and_separators():
    headers = ["VIAJE-ID", "Fecha  Inicio", "fecha_fin", "Estación Origen", "estación.destino"]
    mapping = column_mapping(headers, TRIP_ALIASES)
    assert set(mapping.values()) == set(TRIP_ALIASES)
    assert mapping["Estación Origen"] == "origin_id"


def test_column_mapping_keeps_extra_columns_out_of_the_result():
    mapping = column_mapping([*TRIP_HEADERS, "Usuario Id", "Año de nacimiento"], TRIP_ALIASES)
    assert "Usuario Id" not in mapping
    assert "Año de nacimiento" not in mapping


def test_column_mapping_prefers_the_first_alias_when_several_match():
    mapping = column_mapping([*TRIP_HEADERS, "trip_id"], TRIP_ALIASES)
    assert mapping["Viaje Id"] == "trip_id"
    assert "trip_id" not in mapping


def test_column_mapping_missing_column_names_target_and_headers():
    headers = TRIP_HEADERS[:-1]
    with pytest.raises(ValueError, match="destination_id") as error:
        column_mapping(headers, TRIP_ALIASES)
    assert "Origen Id" in str(error.value)


def test_column_mapping_rejects_empty_headers():
    with pytest.raises(ValueError, match="Falta la columna requerida"):
        column_mapping([], TRIP_ALIASES)


# ---------------------------------------------------------------------------
# csv_format: procesamiento de datos
# ---------------------------------------------------------------------------
ROWS = ["id{sep}nombre{sep}capacidad", "1{sep}Niños Héroes{sep}20", "2{sep}Centro{sep}15"]


def write_csv(path, separator, encoding, prefix=b""):
    text = "\n".join(row.format(sep=separator) for row in ROWS) + "\n"
    path.write_bytes(prefix + text.encode(encoding))
    return path


@pytest.mark.parametrize(
    ("separator", "encoding", "expected_encoding"),
    [
        (",", "utf-8", "utf-8-sig"),
        (";", "cp1252", "cp1252"),
        ("\t", "utf-8", "utf-8-sig"),
    ],
    ids=["utf8-coma", "cp1252-punto-y-coma", "utf8-tabulador"],
)
def test_csv_format_detects_encoding_and_separator(
    tmp_path, separator, encoding, expected_encoding
):
    path = write_csv(tmp_path / "datos.csv", separator, encoding)
    assert csv_format(path) == (expected_encoding, separator)


def test_csv_format_accepts_byte_order_mark(tmp_path):
    path = write_csv(tmp_path / "bom.csv", ",", "utf-8", prefix=b"\xef\xbb\xbf")
    assert csv_format(path) == ("utf-8-sig", ",")


def test_csv_format_falls_back_to_latin1_for_bytes_undefined_in_cp1252(tmp_path):
    path = tmp_path / "latin1.csv"
    path.write_bytes(b"id;nombre\n1;a\x81b\n2;c\n")
    assert csv_format(path) == ("latin-1", ";")


# ---------------------------------------------------------------------------
# canonical_hash y data_path: utilidades
# ---------------------------------------------------------------------------
def test_canonical_hash_does_not_depend_on_key_order():
    first = {"data_version": "1", "files": {"a": 1, "b": 2}}
    second = {"files": {"b": 2, "a": 1}, "data_version": "1"}
    assert canonical_hash(first) == canonical_hash(second)


def test_canonical_hash_is_a_sha256_hex_digest_with_unicode():
    digest = canonical_hash({"estación": "Niños Héroes"})
    assert len(digest) == 64
    assert int(digest, 16) >= 0


@pytest.mark.parametrize(
    "changed",
    [{"a": 2}, {"a": 1, "b": None}, {"a": "1"}],
    ids=["otro-valor", "llave-extra", "otro-tipo"],
)
def test_canonical_hash_changes_when_content_changes(changed):
    assert canonical_hash({"a": 1}) != canonical_hash(changed)


def test_canonical_hash_keeps_list_order():
    assert canonical_hash({"files": [1, 2]}) != canonical_hash({"files": [2, 1]})


def test_data_path_moves_path_under_another_data_dir(tmp_path):
    moved = cfg.data_path(cfg.FEATURE_FILES["p1"], tmp_path)
    assert moved == tmp_path / "processed" / "p1_hourly.parquet"


def test_data_path_with_default_dir_returns_same_path():
    assert cfg.data_path(cfg.RAW_DIR) == cfg.RAW_DIR


def test_data_path_rejects_paths_outside_data_dir(tmp_path):
    with pytest.raises(ValueError):
        cfg.data_path(Path(cfg.ROOT_DIR) / "README.md", tmp_path)
