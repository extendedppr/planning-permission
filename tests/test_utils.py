import os
import unittest
from datetime import date, datetime
from types import SimpleNamespace

from peewee import CharField, Model, SqliteDatabase

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

    def test_search_is_reusable_with_selected_databases(self):
        application = SimpleNamespace(
            address="13 Grand Canal Street, Dublin",
            application_number="1234/24",
            application_status="Decided",
            application_type="Permission",
            decision="Granted",
            received_date=date(2024, 1, 1),
            decision_date=date(2024, 2, 1),
            development_description="Build an extension",
        )

        class FakeDatabase:
            def filter(self, **kwargs):
                self.filter_args = kwargs
                return [application]

        database = FakeDatabase()
        results = utils.search(
            "13, Grand Canal",
            ["Docklands"],
            databases=[("cork", database)],
        )

        self.assertEqual(results[0]["application_number"], "1234/24")
        self.assertEqual(results[0]["address"], application.address)
        self.assertEqual(
            database.filter_args,
            {
                "address_substrs": ["13", "grandcanal"],
                "exclude_address_substrs": ["docklands"],
                "partial": True,
            },
        )

    def test_search_schema_adds_missing_fields(self):
        test_database = SqliteDatabase(":memory:")
        test_database.connect()
        test_database.execute_sql(
            "CREATE TABLE application (id INTEGER PRIMARY KEY, address TEXT)"
        )
        test_database.execute_sql(
            "INSERT INTO application (address) VALUES ('Main Street')"
        )

        class Application(Model):
            address = CharField()
            received_date = CharField(null=True)

            class Meta:
                database = test_database
                table_name = "application"

        database = SimpleNamespace(db=test_database)
        utils._ensure_search_schema(database, Application)

        self.assertEqual(Application.get().address, "Main Street")
        self.assertIsNone(Application.get().received_date)


if __name__ == "__main__":
    unittest.main()
