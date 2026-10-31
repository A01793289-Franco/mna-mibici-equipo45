"""Pruebas PyTest de ``hourly_counts``: la cuadrícula horaria base de P1-P3."""

import pandas as pd
import pytest

from mibici.features import hourly_counts, local_time

START, END = "2026-01-01", "2026-01-02"


def events(rows):
    """Eventos como los de ``load_events``: estación, instante, salidas y llegadas."""
    frame = pd.DataFrame(rows, columns=["station_id", "timestamp", "departures", "arrivals"])
    frame["timestamp"] = frame.timestamp.map(local_time)
    return frame


@pytest.fixture
def two_stations():
    return events(
        [
            (1, "2026-01-01 00:10", 1, 0),
            (1, "2026-01-01 00:50", 2, 1),
            (1, "2026-01-01 03:05", 0, 4),
            (2, "2026-01-01 10:30", 1, 0),
        ]
    )


def test_events_in_the_same_hour_are_added(two_stations):
    counts = hourly_counts(two_stations, START, END)
    first = counts[(counts.station_id == 1) & (counts.timestamp == local_time(START))]
    assert first[["departures", "arrivals"]].to_numpy().tolist() == [[3, 1]]


def test_hours_without_events_are_filled_with_zero(two_stations):
    counts = hourly_counts(two_stations, START, END)
    station = counts[counts.station_id == 1].set_index("timestamp")
    assert len(station) == 24
    assert station.loc[local_time("2026-01-01 01:00"), "departures"] == 0
    assert station.loc[local_time("2026-01-01 03:00"), "arrivals"] == 4


def test_station_starts_at_its_first_observed_hour(two_stations):
    counts = hourly_counts(two_stations, START, END)
    station = counts[counts.station_id == 2]
    assert station.timestamp.min() == local_time("2026-01-01 10:00")
    assert len(station) == 14


def test_totals_are_preserved(two_stations):
    counts = hourly_counts(two_stations, START, END)
    assert counts.departures.sum() == two_stations.departures.sum()
    assert counts.arrivals.sum() == two_stations.arrivals.sum()


def test_one_row_per_station_and_hour_with_int32_counts(two_stations):
    counts = hourly_counts(two_stations, START, END)
    assert not counts.duplicated(["station_id", "timestamp"]).any()
    assert counts[["station_id", "departures", "arrivals"]].dtypes.eq("int32").all()
    assert counts.index.equals(pd.RangeIndex(len(counts)))


def test_end_of_period_is_excluded():
    frame = events([(1, "2026-01-01 22:30", 1, 0), (1, END, 5, 5)])
    counts = hourly_counts(frame, START, END)
    assert counts.timestamp.max() == local_time("2026-01-01 23:00")
    assert counts.departures.sum() == 1


def test_event_exactly_on_the_hour_belongs_to_that_hour():
    frame = events([(1, "2026-01-01 05:00", 1, 0)])
    counts = hourly_counts(frame, START, END)
    assert counts.loc[counts.departures == 1, "timestamp"].tolist() == [
        local_time("2026-01-01 05:00")
    ]


def test_input_events_are_not_modified(two_stations):
    original = two_stations.copy()
    hourly_counts(two_stations, START, END)
    pd.testing.assert_frame_equal(two_stations, original)
