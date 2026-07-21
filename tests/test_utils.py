import os
import unittest
from datetime import date, datetime

os.environ.setdefault(
    "PLANNING_PERMISSION_DATA_LOCATION", "/tmp/planning_permission_unittest"
)

from planning_permission import utils


class UtilsTest(unittest.TestCase):
    def test_convert_date_supports_known_formats(self):
        self.assertEqual(utils.convert_date("01/02/2024"), datetime(2024, 2, 1))
        self.assertEqual(
            utils.convert_date("2024-02-01 13:14:15"),
            datetime(2024, 2, 1, 13, 14, 15),
        )
        self.assertEqual(
            utils.convert_date("2024-02-01 13:14:15.123456"),
            datetime(2024, 2, 1, 13, 14, 15, 123456),
        )

    def test_convert_date_returns_datetime_unchanged(self):
        value = datetime(2024, 2, 1, 13, 14, 15)

        self.assertIs(utils.convert_date(value), value)

    def test_is_nan_treats_none_and_float_nan_as_missing(self):
        self.assertTrue(utils.is_nan(None))
        self.assertTrue(utils.is_nan(float("nan")))
        self.assertFalse(utils.is_nan(0))
        self.assertFalse(utils.is_nan("nan"))

    def test_web_mercator_to_lat_lng_converts_origin(self):
        lat, lng = utils.web_mercator_to_lat_lng(0, 0)

        self.assertEqual(lat, 0)
        self.assertEqual(lng, 0)

    def test_itm_to_lat_lng_converts_false_origin(self):
        lat, lng = utils.itm_to_lat_lng(600000, 750000)

        self.assertAlmostEqual(lat, 53.5, places=6)
        self.assertAlmostEqual(lng, -8, places=6)

    def test_clean_address_for_comparison_normalises_common_tokens(self):
        self.assertEqual(
            utils.clean_address_for_comparison("12 County Road, Main Street (Dublin)."),
            "12cordmainstdublin",
        )
        self.assertEqual(
            utils.clean_address_for_comparison("Avenue House"),
            "avehouse",
        )

    def test_ngrams_uses_lowercase_letters_only(self):
        self.assertEqual(
            utils.ngrams("A-B c!", 2),
            {"ab", "bc"},
        )

    def test_ngrams_honours_requested_count(self):
        self.assertEqual(
            utils.ngrams("abcd", 3),
            {"abc", "bcd"},
        )

    def test_parse_date_returns_date_for_gmt_string(self):
        self.assertEqual(
            utils.parse_date("Mon, 01 Jan 2024 13:14:15 GMT"),
            date(2024, 1, 1),
        )
        self.assertIsNone(utils.parse_date(None))

    def test_normalise_maps_fields_and_parses_selected_dates(self):
        result = utils.normalise(
            {
                "Name": "Planning app",
                "Received": "Mon, 01 Jan 2024 13:14:15 GMT",
                "Ignored": "value",
            },
            {
                "Name": "name",
                "Received": "received_date",
                "Missing": "missing",
            },
            date_fields={"received_date"},
        )

        self.assertEqual(
            result,
            {
                "name": "Planning app",
                "received_date": date(2024, 1, 1),
                "missing": None,
            },
        )

    def test_min_set_cover_can_calculate_without_precomputed_values(self):
        result = utils.min_set_cover(["abc", "cde"], count=2, use_precalculated=False)

        self.assertEqual(len(result), 2)
        self.assertTrue(set(result).issubset({"ab", "bc", "cd", "de"}))


if __name__ == "__main__":
    unittest.main()
