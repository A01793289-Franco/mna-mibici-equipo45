from contextlib import redirect_stdout
from datetime import date
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from mibici import config as cfg
from mibici.dataset import ingest, local_dates, normalize_trips, source_hash, verify_manifest
from mibici.features import (
    load_events,
    p1_features,
    station_profiles,
    temporal_split,
    virtual_occupancy,
)


class Response:
    def __init__(self, body):
        self.body = body
        self.text = body.decode("utf-8", errors="replace")

    def raise_for_status(self):
        pass

    def iter_content(self, size):
        yield self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class Session:
    def get(self, url, **kwargs):
        if url == cfg.DATA_PORTAL_URL:
            return Response(b'<a href="/fixture/datos_abiertos_2026_01.csv">Enero</a>')
        if "nomenclatura" in url:
            return Response(
                b"id,name,latitude,longitude,dpcapacity\n1,Estacion,20.67,-103.35,20\n"
            )
        return Response(
            (
                "Viaje Id;Usuario Id;Año de nacimiento;Inicio del viaje;Fin del viaje;Origen Id;Destino Id\n"
                "1;privado;1990;2026-01-02 10:00:00;2026-01-02 10:10:00;1;1\n"
                "2;privado;1990;2026-01-03 10:00:00;2026-01-03 10:10:00;1;1\n"
                "1;privado;1990;2026-01-02 10:00:00;2026-01-02 10:10:00;1;1\n"
            ).encode("cp1252")
        )

    def close(self):
        pass


def sample_hourly(days=28):
    hours = pd.date_range("2026-01-01", periods=24 * days, freq="h", tz=cfg.TIMEZONE)
    return pd.DataFrame(
        {"station_id": 1, "timestamp": hours, "departures": np.arange(len(hours)), "arrivals": 0}
    )


class TestIngestion(unittest.TestCase):
    def test_source_version_ignores_windows_line_endings(self):
        with tempfile.TemporaryDirectory() as temporary:
            first, second = Path(temporary) / "unix.py", Path(temporary) / "windows.py"
            first.write_bytes(b"x = 1\ny = 2\n")
            second.write_bytes(b"x = 1\r\ny = 2\r\n")
            self.assertEqual(source_hash(first), source_hash(second))

    def test_iso_does_not_swap_month_and_day(self):
        values = pd.Series(
            [
                "2026-01-02 10:00:00",
                "02/01/2026 10:00:00",
                "2026-01-02T16:00:00Z",
                "2026-02-30 10:00:00",
            ],
            dtype="string",
        )
        parsed = local_dates(values)
        self.assertEqual(parsed.iloc[0], parsed.iloc[1])
        self.assertEqual(parsed.iloc[0], parsed.iloc[2])
        self.assertEqual(parsed.iloc[0].month, 1)
        self.assertTrue(pd.isna(parsed.iloc[3]))

    def test_invalid_rows_and_personal_columns(self):
        frame = pd.DataFrame(
            {
                "viaje_id": ["1", "2", "3"],
                "usuario_id": ["privado"] * 3,
                "inicio_del_viaje": ["2026-01-02 10:00:00"] * 3,
                "fin_del_viaje": ["2026-01-02 10:10:00", "2026-01-01 10:00:00", "invalido"],
                "origen_id": ["1"] * 3,
                "destino_id": ["1"] * 3,
            },
            dtype="string",
        )
        clean, counts = normalize_trips(
            frame,
            pd.Timestamp("2026-01-01", tz=cfg.TIMEZONE),
            pd.Timestamp("2026-02-01", tz=cfg.TIMEZONE),
            set(),
        )
        self.assertEqual(len(clean), 1)
        self.assertEqual(counts["invalid"], 2)
        self.assertNotIn("usuario_id", clean.columns)

    def test_repeatable_manifest_and_corruption_detection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                patch("mibici.dataset.http_session", return_value=Session()),
                patch.object(cfg, "CHUNK_ROWS", 1),
                redirect_stdout(io.StringIO()),
            ):
                first = ingest(
                    date(2026, 1, 1), date(2026, 2, 1), root / "data", root / "manifest.json"
                )
                second = ingest(
                    date(2026, 1, 1), date(2026, 2, 1), root / "data", root / "manifest.json"
                )
            self.assertEqual(first, second)
            self.assertEqual(first["summary"]["clean_trips"], 2)
            self.assertEqual(first["trips"][0]["duplicates"], 1)
            self.assertEqual(first["trips"][0]["encoding"], "cp1252")
            path = root / "data" / first["trips"][0]["clean_path"]
            self.assertNotIn("usuario_id", pd.read_parquet(path).columns)
            path.write_bytes(b"modificado")
            with self.assertRaisesRegex(ValueError, "modificado"):
                verify_manifest(first, root / "data")


class TestTemporalFeatures(unittest.TestCase):
    def test_future_departures_cannot_change_current_predictors(self):
        frame = sample_hourly()
        original = p1_features(frame)
        cutoff = frame.timestamp.iloc[240]
        changed = frame.copy()
        changed.loc[changed.timestamp >= cutoff, "departures"] += 10000
        updated = p1_features(changed)
        columns = ["station_id", "timestamp", *cfg.P1_FEATURE_COLUMNS]
        assert_frame_equal(
            original.loc[original.timestamp <= cutoff, columns],
            updated.loc[updated.timestamp <= cutoff, columns],
        )
        self.assertNotEqual(
            original.loc[original.timestamp == cutoff, "target_departures"].iloc[0],
            updated.loc[updated.timestamp == cutoff, "target_departures"].iloc[0],
        )

    def test_lags_do_not_cross_stations(self):
        first = sample_hourly()
        second = first.assign(station_id=2, departures=999)
        result = p1_features(pd.concat([first, second], ignore_index=True))
        self.assertTrue((result.loc[result.station_id == 2, "departures_lag_168"] == 999).all())

    def test_temporal_boundaries_and_crossing_horizons(self):
        times = pd.Series(
            pd.to_datetime(
                ["2026-06-30 23:00", "2026-07-01 00:00", "2026-08-31 23:00", "2026-09-01 00:00"]
            ).tz_localize(cfg.TIMEZONE)
        )
        self.assertEqual(temporal_split(times).tolist(), ["train", "val", "val", "test"])
        with patch.object(cfg, "HORIZON_HOURS", 2):
            self.assertEqual(temporal_split(times).iloc[0], "excluded")

    def test_virtual_inventory_clips_each_event_and_excludes_boundary(self):
        events = pd.DataFrame(
            {
                "station_id": [1, 1, 1],
                "timestamp": pd.to_datetime(
                    ["2026-01-01 00:10", "2026-01-01 00:20", "2026-01-01 01:00"]
                ).tz_localize(cfg.TIMEZONE),
                "departures": [10, 0, 0],
                "arrivals": [0, 1, 1],
            }
        )
        keys = pd.DataFrame(
            {
                "station_id": [1, 1],
                "timestamp": pd.date_range("2026-01-01", periods=2, freq="h", tz=cfg.TIMEZONE),
            }
        )
        current, future, clipped = virtual_occupancy(
            events, keys, pd.DataFrame({"station_id": [1], "capacity": [4]})
        )
        np.testing.assert_allclose(current, [0.5, 0.25])
        np.testing.assert_allclose(future, [0.25, 0.5])
        self.assertEqual(clipped, 1)

    def test_arrivals_are_not_available_before_trip_end(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "month.parquet"
            pd.DataFrame(
                {
                    "origin_id": [1],
                    "destination_id": [2],
                    "started_at": [pd.Timestamp("2026-01-01 01:00", tz=cfg.TIMEZONE)],
                    "ended_at": [pd.Timestamp("2026-01-01 05:00", tz=cfg.TIMEZONE)],
                }
            ).to_parquet(path)
            events = load_events(
                {
                    "start": "2026-01-01",
                    "end_exclusive": "2026-01-02",
                    "trips": [{"clean_path": path.name}],
                },
                temporary,
            )
            arrival = events[events.arrivals == 1].iloc[0]
            self.assertEqual(arrival.timestamp.hour, 5)

    def test_station_profiles_ignore_future_and_normalize(self):
        frame = sample_hourly()
        frame["departures"] = np.where(frame.timestamp.dt.dayofweek < 5, 9, 3)
        stations = pd.DataFrame(
            {"station_id": [1], "name": ["A"], "latitude": [20.67], "longitude": [-103.35]}
        )
        original = station_profiles(frame, stations, "2026-01-01", "2026-01-22")
        changed = frame.copy()
        changed.loc[
            changed.timestamp >= pd.Timestamp("2026-01-22", tz=cfg.TIMEZONE), "departures"
        ] = 99999
        updated = station_profiles(changed, stations, "2026-01-01", "2026-01-22")
        assert_frame_equal(original, updated)
        self.assertAlmostEqual(original[list(cfg.P3_FEATURE_COLUMNS)].sum(axis=1).iloc[0], 1)
        self.assertAlmostEqual(original.weekday_00.iloc[0], 9 / (24 * 12))


if __name__ == "__main__":
    unittest.main()
