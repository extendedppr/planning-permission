import importlib.util
import os
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault(
    "PLANNING_PERMISSION_DATA_LOCATION", "/tmp/planning_permission_unittest"
)

from planning_permission.cork import CorkObject, cork_db
from planning_permission.dcc import DCCObject, dcc_db
from planning_permission.galway import GalwayObject, galway_db
from planning_permission.planning_permission_db import (
    PlanningPermissionObject,
    planning_permission_db,
)


def load_search_module():
    search_path = Path(__file__).resolve().parents[1] / "scripts" / "search.py"
    spec = importlib.util.spec_from_file_location("search", search_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


search = load_search_module()


LONG_DESCRIPTION = (
    "Build extension with a very long description that should clearly exceed "
    "fifty characters"
)


class SearchTest(unittest.TestCase):
    def setUp(self):
        planning_permission_db.recreate()
        dcc_db.recreate()
        cork_db.recreate()
        galway_db.recreate()

    def tearDown(self):
        planning_permission_db.recreate()
        dcc_db.recreate()
        cork_db.recreate()
        galway_db.recreate()

    def seed_search_rows(self):
        PlanningPermissionObject.parse(
            {
                "development_address": "13 Grand Canal, Dublin",
                "planning_authority": "Dublin City Council",
                "application_number": "G1",
                "development_description": LONG_DESCRIPTION,
                "application_status": "Granted",
                "application_type": "Permission",
                "decision": "Grant",
            }
        ).save()
        DCCObject.parse(
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
                "description": "Cork planning description",
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
        with patch.object(sys, "argv", ["search", *args]):
            with redirect_stdout(output):
                search.main()
        return output.getvalue()

    def test_default_search_compiles_results_from_all_sources(self):
        self.seed_search_rows()

        output = self.run_search("--address-substr-csv", "13,grand canal")

        self.assertIn("general", output)
        self.assertIn("dublin", output)
        self.assertIn("cork", output)
        self.assertIn("galway", output)
        self.assertIn("G1", output)
        self.assertIn("C1", output)
        self.assertIn("GA1", output)

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

        self.assertIn("general", output)
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

        self.assertIn("development_description", output)
        self.assertIn(LONG_DESCRIPTION, output)
        self.assertNotIn(
            "Build extension with a very long description that ...", output
        )


if __name__ == "__main__":
    unittest.main()
