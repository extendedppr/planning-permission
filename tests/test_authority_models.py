import os
import unittest

os.environ.setdefault(
    "PLANNING_PERMISSION_DATA_LOCATION", "/tmp/planning_permission_unittest"
)

from planning_permission.cork import CorkObject, cork_db
from planning_permission.galway import GalwayObject, galway_db


class AuthorityModelTest(unittest.TestCase):
    def test_cork_object_persists_fields_from_download_comment(self):
        cork_db.recreate()

        CorkObject.parse(
            {
                "address": "GLEN HOUSE, OLD WHITECHURCH ROAD, CORK",
                "objid": 12,
                "planning_authority": "Cork City Council",
                "applicant_name": "GERRY CURTIN",
                "application_number": "9923292",
                "received_date": 928368000000,
                "link_app_details": "http://planning.corkcity.ie/AppFileRefDetails/9923292/0",
                "application_type": "PERMISSION",
                "description": "RETENTION OF WORKSHOP & STORE",
                "development_address": "GLEN HOUSE, OLD WHITECHURCH RD, TURNERS CROSS",
                "decision": "CONDITIONAL",
                "application_status": "APPLICATION FINALISED",
                "decision_date": 933120000000,
                "file_year": 1999,
                "number_conditions": 6,
                "global_id": "150fe94e-77c4-43dd-816a-cca3aadf5fe8",
                "shape_area": 12380.243927001953,
                "shape_length": 656.9289782867681,
                "geometry": '{"rings": []}',
            }
        ).save()

        saved = CorkObject.get(CorkObject.objid == 12)

        self.assertEqual(saved.application_number, "9923292")
        self.assertEqual(
            saved.development_address,
            "GLEN HOUSE, OLD WHITECHURCH RD, TURNERS CROSS",
        )
        self.assertEqual(saved.decision_date, "933120000000")
        self.assertEqual(saved.number_conditions, 6)
        self.assertEqual(saved.shape_area, 12380.243927001953)
        self.assertEqual(saved.geometry, '{"rings": []}')

    def test_galway_object_persists_additional_fields(self):
        galway_db.recreate()

        GalwayObject.parse(
            {
                "address": "Test, Galway",
                "objid": 1,
                "application_number": "2661122",
                "withdrawn_date": "n\\a",
                "appeal_notification_date": "n\\a",
                "appeal_ref_num": "n\\a",
                "lat": 53.547,
                "lng": -8.847,
                "more_info": "http://www.eplanning.ie/GalwayCC/AppFileRefDetails/2661122/0",
                "global_id": "c3c59aa6-4807-41ad-9745-f1a15b0a6d77",
            }
        ).save()

        saved = GalwayObject.get(GalwayObject.objid == 1)

        self.assertEqual(saved.application_number, "2661122")
        self.assertEqual(saved.appeal_ref_num, "n\\a")
        self.assertEqual(saved.lat, 53.547)
        self.assertEqual(saved.lng, -8.847)
        self.assertEqual(saved.global_id, "c3c59aa6-4807-41ad-9745-f1a15b0a6d77")


if __name__ == "__main__":
    unittest.main()
