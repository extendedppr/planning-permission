import os
import unittest

os.environ.setdefault(
    "PLANNING_PERMISSION_DATA_LOCATION", "/tmp/planning_permission_unittest"
)

from planning_permission.cork import CorkObject, cork_db
from planning_permission.galway import GalwayObject, galway_db
from planning_permission.kildare import KildareObject, kildare_db
from planning_permission.settings import GALWAY_DB_LOCATION, KILDARE_DB_LOCATION


class AuthorityModelTest(unittest.TestCase):
    def test_kildare_uses_its_own_database(self):
        self.assertNotEqual(KILDARE_DB_LOCATION, GALWAY_DB_LOCATION)
        self.assertEqual(KildareObject._meta.database.database, KILDARE_DB_LOCATION)
        self.assertEqual(kildare_db.db.database, KILDARE_DB_LOCATION)

    def test_kildare_object_parses_source_fields(self):
        kildare_db.recreate()

        KildareObject.parse(
            {
                "FileNumber": "2114",
                "LocalAuthority": "Kildare County Council",
                "DateReceived": "11/01/2021",
                "Type": "PERMISSION",
                "SubmissionsBy": "",
                "DueDate": "",
                "Decision": "REFUSE",
                "DecisionDateMO": "03/03/2021",
                "ApplicationStatus": "APPLICATION FINALISED",
                "GrantDate": "01/01/1900",
                "FurtherInfoRequested": "",
                "FurtherInfoReceived": "",
                "ReportFileLocation": "",
                "ApplicantName": "Audrey Timmons & Brendan Rouse",
                "DevelopmentDescription": "construct a house",
                "DevelopmentAddress": "Newtownhortland, Donadea, Naas, Co. Kildare",
                "EngineeringArea": 4,
                "Planner": "Louise Murphy",
                "NumberofAppealstoAnBordPleanala": "",
            }
        ).save()

        saved = KildareObject.get(KildareObject.application_number == "2114")

        self.assertEqual(saved.address, saved.development_address)
        self.assertEqual(saved.planning_authority, "Kildare County Council")
        self.assertEqual(saved.decision_date, "03/03/2021")
        self.assertEqual(saved.engineering_area, 4)
        self.assertEqual(saved.planner, "Louise Murphy")

    def test_kildare_object_parses_legacy_record_without_objid(self):
        obj = KildareObject.parse(
            {
                "FileNumber": "99500035",
                "LocalAuthority": "Kildare County Council",
                "DateReceived": "24/03/1999",
                "Type": "PERMISSION",
                "SubmissionsBy": "",
                "DueDate": "",
                "Decision": "GRANT",
                "DecisionDateMO": "04/08/1999",
                "ApplicationStatus": "DECISION MADE",
                "GrantDate": "01/01/1900",
                "FurtherInfoRequested": "",
                "FurtherInfoReceived": "",
                "ReportFileLocation": "",
                "ApplicantName": "P. Madden",
                "DevelopmentDescription": "construction of extension",
                "DevelopmentAddress": "42 Kingsfurze Avenue,, Naas,, Co. Kildare",
                "EngineeringArea": None,
                "Planner": None,
                "NumberofAppealstoAnBordPleanala": "",
            }
        )

        self.assertEqual(obj.application_number, "99500035")
        self.assertEqual(obj.address, "42 Kingsfurze Avenue,, Naas,, Co. Kildare")
        self.assertEqual(obj.decision_date, "04/08/1999")
        self.assertIsNone(obj.engineering_area)
        self.assertIsNone(obj.planner)

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
