from datetime import date
from hashlib import sha256
from pathlib import Path
import shutil

import pytest
import requests

from mibici import config as cfg
from mibici.dataset import discover_stations, download_stations, ingest, verify_manifest

OLD = "https://www.mibici.net/fixture/nomenclatura_2026_09.csv"
CURRENT = "https://www.mibici.net/fixture/nomenclatura_2026_10.csv"
TRIPS_URL = "https://www.mibici.net/fixture/datos_abiertos_2026_01.csv"
CATALOG = b"id,name,latitude,longitude,dpcapacity\n1,Centro,20.67,-103.35,20\n"
UPDATED = CATALOG.replace(b",20\n", b",30\n")
TRIPS = (
    b"Viaje Id,Inicio del viaje,Fin del viaje,Origen Id,Destino Id\n"
    b"1,2026-01-08 10:00:00,2026-01-08 10:10:00,1,1\n"
)


class Session:
    def __init__(self, old_status=200, links=None):
        self.old_status = old_status
        self.links = links if links is not None else [TRIPS_URL, CURRENT]
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        response = requests.Response()
        response.url = url
        response.status_code = self.old_status if url == OLD else 200
        response._content_consumed = True
        if url == cfg.DATA_PORTAL_URL:
            response._content = "".join(
                f'<a href="{link}">CSV</a>' for link in self.links
            ).encode()
        elif url == TRIPS_URL:
            response._content = TRIPS
        else:
            response._content = CATALOG if url == OLD else UPDATED
        return response

    def close(self):
        pass


def recorded():
    return {
        "stations": {
            "url": OLD,
            "raw_path": "raw/" + Path(OLD).name,
            "raw_sha256": sha256(CATALOG).hexdigest(),
        }
    }


def test_discovery_uses_latest_valid_catalog_from_official_host():
    session = Session(
        links=[
            OLD,
            CURRENT,
            TRIPS_URL,
            "https://otro.example/nomenclatura_2099_01.csv",
            "https://www.mibici.net/fixture/nomenclatura_2099_13.csv",
            "https://www.mibici.net/fixture/nomenclatura_2026_11.csv?download=1",
        ]
    )
    assert discover_stations(session).endswith("nomenclatura_2026_11.csv?download=1")


def test_discovery_reports_missing_catalog():
    with pytest.raises(ValueError, match="--stations-url"):
        discover_stations(Session(links=[TRIPS_URL]))


def test_first_ingestion_discovers_catalog_without_hardcoded_month(tmp_path):
    session = Session()
    url, raw = download_stations(session, tmp_path, {})
    assert url == CURRENT
    assert raw.read_bytes() == UPDATED
    assert session.calls == [cfg.DATA_PORTAL_URL, CURRENT]


@pytest.mark.parametrize("status", [404, 410])
def test_retired_recorded_catalog_is_replaced_and_announced(tmp_path, capsys, status):
    session = Session(old_status=status)
    url, raw = download_stations(session, tmp_path, recorded())
    assert url == CURRENT
    assert raw.read_bytes() == UPDATED
    assert "nueva versión de datos" in capsys.readouterr().out
    assert session.calls == [OLD, cfg.DATA_PORTAL_URL, CURRENT]
    assert not list(tmp_path.rglob("*.part"))


def test_cached_historical_catalog_does_not_need_network(tmp_path):
    raw = tmp_path / recorded()["stations"]["raw_path"]
    raw.parent.mkdir()
    raw.write_bytes(CATALOG)
    session = Session(old_status=404)
    assert download_stations(session, tmp_path, recorded()) == (OLD, raw)
    assert not session.calls


def test_corrupted_cached_catalog_is_not_replaced_silently(tmp_path):
    raw = tmp_path / recorded()["stations"]["raw_path"]
    raw.parent.mkdir()
    raw.write_bytes(b"corrupto")
    session = Session()
    with pytest.raises(ValueError, match="Hash distinto"):
        download_stations(session, tmp_path, recorded())
    assert not session.calls
    assert raw.read_bytes() == b"corrupto"


def test_changed_bytes_at_live_historical_url_fail_hash_verification(tmp_path):
    previous = recorded()
    previous["stations"]["raw_sha256"] = "0" * 64
    session = Session()
    with pytest.raises(ValueError, match="fuente cambió"):
        download_stations(session, tmp_path, previous)
    assert session.calls == [OLD]
    assert not list(tmp_path.rglob("*.csv"))
    assert not list(tmp_path.rglob("*.part"))


@pytest.mark.parametrize("status", [403, 500])
def test_http_errors_other_than_retirement_are_not_hidden(tmp_path, status):
    session = Session(old_status=status)
    with pytest.raises(requests.HTTPError):
        download_stations(session, tmp_path, recorded())
    assert session.calls == [OLD]


def test_explicit_catalog_url_does_not_fall_back(tmp_path):
    session = Session(old_status=404)
    with pytest.raises(requests.HTTPError):
        download_stations(session, tmp_path, recorded(), stations_url=OLD)
    assert session.calls == [OLD]


def test_refresh_discovers_current_catalog(tmp_path):
    session = Session(old_status=404)
    assert download_stations(session, tmp_path, recorded(), refresh=True)[0] == CURRENT
    assert OLD not in session.calls


def test_unavailable_current_catalog_reports_actionable_error(tmp_path):
    with pytest.raises(ValueError, match="--stations-url"):
        download_stations(Session(old_status=404, links=[OLD]), tmp_path, recorded())


def test_empty_directory_recovery_versions_catalog_and_is_repeatable(tmp_path, monkeypatch):
    session = Session()
    monkeypatch.setattr("mibici.dataset.http_session", lambda: session)
    data, manifest = tmp_path / "data", tmp_path / "manifest.json"
    old = ingest(date(2026, 1, 1), date(2026, 2, 1), data, manifest, stations_url=OLD)
    shutil.rmtree(data)
    session.old_status = 404
    current = ingest(date(2026, 1, 1), date(2026, 2, 1), data, manifest)
    assert current["stations"]["url"] == CURRENT
    assert current["stations"]["raw_sha256"] == sha256(UPDATED).hexdigest()
    assert current["data_version"] != old["data_version"]
    assert current["trips"] == old["trips"]
    verify_manifest(current, data)
    session.calls.clear()
    assert ingest(date(2026, 1, 1), date(2026, 2, 1), data, manifest) == current
    assert not session.calls
