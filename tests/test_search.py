import json
import os
import unittest
from contextlib import redirect_stdout
from io import StringIO

os.environ.setdefault(
    "PLANNING_PERMISSION_DATA_LOCATION", "/tmp/planning_permission_unittest"
)

from planning_permission.cork import CorkObject, cork_db
from planning_permission.dublin import DublinObject, dublin_db
from planning_permission.galway import GalwayObject, galway_db
from scripts import search


LONG_DESCRIPTION = (
    "Build extension with a very long description that should clearly exceed "
    "fifty characters"
)


class SearchTest(unittest.TestCase):
    def setUp(self):
        dublin_db.recreate()
        cork_db.recreate()
        galway_db.recreate()

    def tearDown(self):
        dublin_db.recreate()
        cork_db.recreate()
        galway_db.recreate()

    def seed_search_rows(self):
        DublinObject.parse(
            {
                "objid": 1,
                "address": "13 Grand Canal Street, Dublin",
                "proposal": "Alter house",
                "status_description": "Decision Made",
            }
        ).save()
        CorkObject.parse(
            {
                "address": "13 Grand Canal View, Cork",
                "application_number": "C1",
                "application_status": "APPLICATION FINALISED",
                "application_type": "PERMISSION",
                "decision": "CONDITIONAL",
                "description": LONG_DESCRIPTION,
                "link_app_details": "https://example.test/cork",
            }
        ).save()
        GalwayObject.parse(
            {
                "address": "13 Grand Canal View, Galway",
                "application_number": "GA1",
                "application_status": "Granted",
                "application_type": "Permission",
                "description": "Galway planning description",
                "more_info": "https://example.test/galway",
                "global_id": "galway-global-id",
            }
        ).save()

    def run_search(self, *args):
        output = StringIO()
        with redirect_stdout(output):
            search.main(args)
        return output.getvalue()

    def test_default_search_compiles_results_from_all_sources(self):
        self.seed_search_rows()

        output = self.run_search("--address-substr-csv", "13,grand canal")

        self.assertIn("dublin", output)
        self.assertIn("cork", output)
        self.assertIn("galway", output)
        self.assertIn("C1", output)
        self.assertIn("GA1", output)
        self.assertIn("╒", output)

    def test_json_output_returns_parseable_rows(self):
        self.seed_search_rows()

        output = self.run_search(
            "--address-substr-csv",
            "13,grand canal",
            "--output",
            "json",
        )

        rows = json.loads(output)
        self.assertEqual(
            {row["source"] for row in rows},
            {"dublin", "cork", "galway"},
        )
        self.assertIn("C1", {row["application_number"] for row in rows})
        cork = next(row for row in rows if row["source"] == "cork")
        self.assertEqual(cork["description"], LONG_DESCRIPTION)

    def test_default_search_truncates_long_fields_and_hides_more_info(self):
        self.seed_search_rows()

        output = self.run_search("--address-substr-csv", "13,grand canal")

        self.assertIn("Build extension with a very long description that ...", output)
        self.assertNotIn("should clearly exceed fifty characters", output)
        self.assertNotIn("more_info", output)
        self.assertNotIn("https://example.test/cork", output)
        self.assertNotIn("https://example.test/galway", output)

    def test_all_disables_value_truncation(self):
        self.seed_search_rows()

        output = self.run_search("--address-substr-csv", "13,grand canal", "--all")

        self.assertIn(LONG_DESCRIPTION, output)
        self.assertNotIn(
            "Build extension with a very long description that ...", output
        )

    def test_all_features_shows_model_fields(self):
        self.seed_search_rows()

        output = self.run_search(
            "--address-substr-csv",
            "13,grand canal",
            "--all-features",
        )

        self.assertIn("searchable_address", output)
        self.assertIn("global_id", output)
        self.assertIn("galway-global-id", output)

    def test_exclude_address_substrings_filter_all_sources(self):
        self.seed_search_rows()

        output = self.run_search(
            "--address-substr-csv",
            "13,grand canal",
            "--exclude-address-substr-csv",
            "cork,galway",
        )

        self.assertIn("dublin", output)
        self.assertNotIn("cork", output)
        self.assertNotIn("galway", output)
        self.assertNotIn("C1", output)
        self.assertNotIn("GA1", output)

    def test_all_features_with_all_shows_untruncated_model_fields(self):
        self.seed_search_rows()

        output = self.run_search(
            "--address-substr-csv",
            "13,grand canal",
            "--all-features",
            "--all",
        )

        self.assertIn("description", output)
        self.assertIn(LONG_DESCRIPTION, output)
        self.assertNotIn(
            "Build extension with a very long description that ...", output
        )


if __name__ == "__main__":
    unittest.main()
