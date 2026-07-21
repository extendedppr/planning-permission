import os
import unittest

os.environ.setdefault(
    "PLANNING_PERMISSION_DATA_LOCATION", "/tmp/planning_permission_unittest"
)

from planning_permission.planning_permission_db import (
    PlanningPermissionObject,
    planning_permission_db,
)


class PlanningPermissionDBTest(unittest.TestCase):
    def setUp(self):
        planning_permission_db.recreate()

    def tearDown(self):
        planning_permission_db.recreate()

    def test_recreate_resets_general_planning_table(self):
        PlanningPermissionObject.parse(
            {
                "development_address": "13 Grand Canal, Dublin",
                "planning_authority": "Dublin City Council",
                "application_number": "G1",
                "development_description": "Build extension",
                "application_status": "Granted",
                "application_type": "Permission",
            }
        ).save()

        self.assertEqual(len(planning_permission_db), 1)

        planning_permission_db.recreate()

        self.assertEqual(len(planning_permission_db), 0)

    def test_eircode_helpers_use_development_postcode(self):
        obj = PlanningPermissionObject.parse(
            {
                "development_address": "13 Grand Canal, Dublin",
                "planning_authority": "Dublin City Council",
                "application_number": "G1",
                "development_description": "Build extension",
                "development_postcode": "D02AB12",
                "application_status": "Granted",
                "application_type": "Permission",
            }
        )

        self.assertEqual(obj.eircode_routing_key, "d02")
        self.assertEqual(obj.eircode_unique_id, "ab12")

    def test_eircode_helpers_return_none_when_postcode_missing(self):
        obj = PlanningPermissionObject.parse(
            {
                "development_address": "13 Grand Canal, Dublin",
                "planning_authority": "Dublin City Council",
                "application_number": "G1",
                "development_description": "Build extension",
                "application_status": "Granted",
                "application_type": "Permission",
            }
        )

        self.assertIsNone(obj.eircode_routing_key)
        self.assertIsNone(obj.eircode_unique_id)

    def test_filter_by_eircode_uses_development_postcode(self):
        PlanningPermissionObject.parse(
            {
                "development_address": "13 Grand Canal, Dublin",
                "planning_authority": "Dublin City Council",
                "application_number": "G1",
                "development_description": "Build extension",
                "development_postcode": "D02AB12",
                "application_status": "Granted",
                "application_type": "Permission",
            }
        ).save()

        results = planning_permission_db.filter(eircode="D02AB12")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].application_number, "G1")

    def test_filter_by_eircode_routing_key_uses_development_postcode_prefix(self):
        PlanningPermissionObject.parse(
            {
                "development_address": "13 Grand Canal, Dublin",
                "planning_authority": "Dublin City Council",
                "application_number": "G1",
                "development_description": "Build extension",
                "development_postcode": "D02AB12",
                "application_status": "Granted",
                "application_type": "Permission",
            }
        ).save()
        PlanningPermissionObject.parse(
            {
                "development_address": "14 Grand Canal, Dublin",
                "planning_authority": "Dublin City Council",
                "application_number": "G2",
                "development_description": "Build extension",
                "development_postcode": "D04CD34",
                "application_status": "Granted",
                "application_type": "Permission",
            }
        ).save()

        results = planning_permission_db.filter(eircode_routing_key="D02")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].application_number, "G1")


if __name__ == "__main__":
    unittest.main()
