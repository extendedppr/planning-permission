import importlib.util
import os
import unittest
from datetime import date, datetime
from pathlib import Path

os.environ.setdefault(
    "PLANNING_PERMISSION_DATA_LOCATION", "/tmp/planning_permission_unittest"
)


def load_download_module():
    download_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "download_planning_permission.py"
    )
    spec = importlib.util.spec_from_file_location(
        "download_planning_permission", download_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


download_planning_permission = load_download_module()


class DownloadPlanningPermissionTest(unittest.TestCase):
    def test_parse_dcc_date_supports_known_formats(self):
        expected = date(2024, 1, 2)

        self.assertEqual(download_planning_permission.parse_dcc_date(None), None)
        self.assertEqual(
            download_planning_permission.parse_dcc_date(datetime(2024, 1, 2, 3, 4)),
            expected,
        )
        self.assertEqual(
            download_planning_permission.parse_dcc_date("2024-01-02"), expected
        )
        self.assertEqual(
            download_planning_permission.parse_dcc_date("2024-01-02T03:04:05"),
            expected,
        )
        self.assertEqual(
            download_planning_permission.parse_dcc_date("2024-01-02T03:04:05.123456"),
            expected,
        )
        self.assertEqual(
            download_planning_permission.parse_dcc_date(
                "Tue, 02 Jan 2024 03:04:05 GMT"
            ),
            expected,
        )
        self.assertEqual(
            download_planning_permission.parse_dcc_date("2024-01-02T03:04:05Z"),
            expected,
        )

    def test_parse_dcc_application_ignores_404_and_missing_required_fields(self):
        self.assertIsNone(
            download_planning_permission.parse_dcc_application({"status_code": 404})
        )
        self.assertIsNone(
            download_planning_permission.parse_dcc_application(
                {
                    "id": 1,
                }
            )
        )
        self.assertIsNone(
            download_planning_permission.parse_dcc_application(
                {
                    "location": "13 Grand Canal Street, Dublin",
                }
            )
        )

    def test_parse_dcc_application_converts_easting_northing_to_lat_lng(self):
        obj = download_planning_permission.parse_dcc_application(
            {
                "id": 1,
                "location": "13 Grand Canal Street, Dublin",
                "easting": 600000,
                "northing": 750000,
                "registrationDate": "2024-01-02",
            }
        )

        self.assertAlmostEqual(obj.lat, 53.5, places=6)
        self.assertAlmostEqual(obj.lng, -8, places=6)
        self.assertEqual(obj.registration_date, date(2024, 1, 2))
        self.assertFalse(hasattr(obj, "easting"))
        self.assertFalse(hasattr(obj, "northing"))


if __name__ == "__main__":
    unittest.main()
