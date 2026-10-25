"""Pruebas del agrupamiento de estaciones: solo aprende del entrenamiento y no falla con nuevas."""

import unittest

import numpy as np
import pandas as pd

from mibici.stations import GROUP_COLUMN, StationGrouper


def frame(counts):
    """Tabla con ``station_id`` repetido según ``{estación: filas}`` y una variable numérica."""
    ids = np.concatenate([np.full(rows, station) for station, rows in counts.items()])
    return pd.DataFrame({"station_id": ids.astype("int32"), "x": np.arange(len(ids), dtype=float)})


class TestStationGrouper(unittest.TestCase):
    def test_most_frequent_stations_keep_their_own_code(self):
        grouper = StationGrouper(max_categories=4).fit(frame({1: 5, 2: 9, 3: 7, 4: 2, 5: 1}))
        self.assertEqual(grouper.kept_stations_.tolist(), [2, 3, 1])
        self.assertEqual(grouper.other_code_, 3)
        self.assertEqual(grouper.n_categories_, 4)
        self.assertEqual(grouper.n_grouped_stations_, 2)

    def test_transform_replaces_station_id_by_group_and_groups_rest_as_other(self):
        grouper = StationGrouper(max_categories=4).fit(frame({1: 5, 2: 9, 3: 7, 4: 2, 5: 1}))
        result = grouper.transform(frame({2: 1, 3: 1, 1: 1, 4: 1, 5: 1}))
        self.assertNotIn("station_id", result.columns)
        self.assertEqual(result[GROUP_COLUMN].tolist(), [0, 1, 2, 3, 3])

    def test_unseen_station_goes_to_other_without_failing(self):
        grouper = StationGrouper(max_categories=4).fit(frame({1: 5, 2: 9, 3: 7}))
        result = grouper.transform(frame({999: 2}))
        self.assertEqual(result[GROUP_COLUMN].tolist(), [3, 3])

    def test_mapping_is_learned_only_from_fit_data(self):
        training = frame({1: 5, 2: 9, 3: 7})
        grouper = StationGrouper(max_categories=3).fit(training)
        before = grouper.kept_stations_.copy()
        grouper.transform(frame({4: 1000, 5: 1000}))  # datos "de validación" muy frecuentes
        np.testing.assert_array_equal(grouper.kept_stations_, before)
        self.assertEqual(before.tolist(), [2, 3])

    def test_ties_are_broken_by_station_id(self):
        grouper = StationGrouper(max_categories=3).fit(frame({7: 4, 3: 4, 5: 4}))
        self.assertEqual(grouper.kept_stations_.tolist(), [3, 5])

    def test_never_exceeds_the_boosting_category_limit(self):
        many = frame({station: 2 for station in range(1, 472)})
        grouper = StationGrouper().fit(many)
        codes = grouper.transform(many)[GROUP_COLUMN]
        self.assertLessEqual(codes.max() + 1, 255)
        self.assertEqual(grouper.n_grouped_stations_, 471 - 254)


if __name__ == "__main__":
    unittest.main()
