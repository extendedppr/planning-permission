import os
import unittest
from unittest.mock import Mock, call, patch

os.environ.setdefault(
    "PLANNING_PERMISSION_DATA_LOCATION", "/tmp/planning_permission_unittest"
)

from planning_permission.cork import CorkObject, cork_db
from planning_permission import clare
from planning_permission.donegal import DonegalObject, donegal_db
from planning_permission.wexford import (
    WexfordObject,
    _parse_wexford_dates,
    _wexford_application_id,
    wexford_db,
)
from planning_permission.kerry import KerryObject, kerry_db
from planning_permission.wicklow import WicklowObject, wicklow_db
from planning_permission.louth import LouthObject, louth_db
from planning_permission.mayo import MayoObject, mayo_db
from planning_permission.clare import ClareObject, clare_db
from planning_permission.waterford import WaterfordObject, waterford_db
from planning_permission.galway import GalwayObject, galway_db
from planning_permission.kildare import KildareObject, kildare_db
from planning_permission.limerick import LimerickObject, limerick_db
from planning_permission.meath import MeathObject, meath_db
from planning_permission.tipperary import TipperaryObject, tipperary_db
from planning_permission.settings import (
    GALWAY_DB_LOCATION,
    KILDARE_DB_LOCATION,
    MEATH_DB_LOCATION,
    LIMERICK_DB_LOCATION,
    TIPPERARY_DB_LOCATION,
    DONEGAL_DB_LOCATION,
    WEXFORD_DB_LOCATION,
    KERRY_DB_LOCATION,
    WICKLOW_DB_LOCATION,
    LOUTH_DB_LOCATION,
    MAYO_DB_LOCATION,
    CLARE_DB_LOCATION,
    WATERFORD_DB_LOCATION,
)


class AuthorityModelTest(unittest.TestCase):
    def test_clare_download_avoids_unsupported_arcgis_sort(self):
        site = {
            "OBJECTID": 1,
            "OBJECTID_1": 2,
            "FileNumber": "001009",
            "ApplicationType": "PERMISSION",
        }
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = """
        <div id="planningApplicationDetails">
          <div id="Details"><table>
            <tr><th>File Number:</th><td>001009</td></tr>
          </table></div>
          <div id="Applicant"><table></table></div>
          <div id="Development"><table></table></div>
          <div id="Decision"><table>
            <tr><th>Decision Type:</th><td>CONDITIONAL</td></tr>
          </table></div>
        </div>
        """
        with (
            patch.object(clare, "arcgis_download", return_value=[site]) as download,
            patch.object(clare, "_mayo_request", return_value=response),
            patch.object(clare, "write_to_db") as write,
        ):
            clare.download_clare()

        self.assertEqual(
            download.call_args_list,
            [
                call(clare.CLARE_SITES_URL, skip_sort=True, prefix="Clare sites: "),
            ],
        )
        self.assertEqual(write.call_args.args[2][0].decision, "CONDITIONAL")

    def test_waterford_object_parses_full_register_fields(self):
        waterford_db.recreate()
        WaterfordObject.parse(
            {
                "OBJECTID": 991751,
                "ApplicationNumber": "10323",
                "PlanningAuthority": "Waterford City and County Council",
                "ReceivedDate": "26/08/2010",
                "ApplicationStatus": "Application Finalised",
                "ApplicationType": "PERMISSION",
                "ApplicantName": "Colm & Ruth Heylin",
                "Description": "construct an extension",
                "Location": "Rose Cottage  Five Cross Road Hacketstown",
                "Decision": "Granted (Conditional)",
                "DecisionDate": "18/10/2010",
                "DecisionDueDate": "20/10/2010",
                "LinkAppDetails": "http://example.test/10323",
                "ITMEasting": 645640.05,
                "ITMNorthing": 611493.24,
                "fme_datecreated": 20251119,
            }
        ).save()
        saved = WaterfordObject.get_by_id(1)
        self.assertEqual(WaterfordObject._meta.database.database, WATERFORD_DB_LOCATION)
        self.assertEqual(saved.application_number, "10323")
        self.assertEqual(saved.address, "Rose Cottage Five Cross Road Hacketstown")
        self.assertEqual(saved.decision, "Granted (Conditional)")

    def test_clare_object_parses_national_register_fields(self):
        clare_db.recreate()
        ClareObject.parse(
            {
                "OBJECTID": 2409,
                "OBJECTID_1": 5926156,
                "FileNumber": "001009",
                "ApplicationType": "PERMISSION",
                "SiteID": 123,
            },
            {
                "ApplicationNumber": "001009",
                "DevelopmentAddress": "Main Street, Ennis",
                "PlanningAuthority": "Clare County Council",
                "ApplicationType": "PERMISSION",
                "ApplicationStatus": "Application Finalised",
                "DevelopmentDescription": "Build a dwelling",
                "Decision": "CONDITIONAL",
                "ReceivedDate": 1704067200000,
                "DecisionDate": 1709251200000,
                "LinkAppDetails": "https://example.test/001009",
            },
        ).save()
        saved = ClareObject.get_by_id(1)
        self.assertEqual(ClareObject._meta.database.database, CLARE_DB_LOCATION)
        self.assertEqual(saved.objid, 5926156)
        self.assertEqual(saved.source_object_id, 2409)
        self.assertEqual(saved.application_number, "001009")
        self.assertEqual(saved.application_type, "PERMISSION")
        self.assertEqual(saved.address, "Main Street, Ennis")
        self.assertEqual(saved.decision, "CONDITIONAL")

    def test_mayo_object_parses_national_arcgis_fields(self):
        mayo_db.recreate()
        MayoObject.parse(
            {
                "OBJECTID": 326004,
                "PlanningAuthority": "Mayo County Council",
                "ApplicationNumber": "17515",
                "DevelopmentAddress": "DRUMNEEN MORE, CASTLEBAR",
                "DevelopmentDescription": "EXTEND AND RENOVATE DWELLING",
                "ApplicationStatus": "APPLICATION FINALISED",
                "ApplicationType": "PERMISSION",
                "ApplicantForename": "Test",
                "ApplicantSurname": "Applicant",
                "Decision": "CONDITIONAL",
                "ReceivedDate": 1498694400000,
                "DecisionDate": 1503273600000,
                "NumResidentialUnits": 0,
                "LinkAppDetails": "http://example.test/mayo/17515",
            }
        ).save()
        saved = MayoObject.get_by_id(1)
        self.assertEqual(MayoObject._meta.database.database, MAYO_DB_LOCATION)
        self.assertEqual(saved.application_number, "17515")
        self.assertEqual(saved.applicant_name, "Test Applicant")
        self.assertEqual(saved.received_date, 1498694400000)
        self.assertEqual(saved.address, "DRUMNEEN MORE, CASTLEBAR")

    def test_mayo_object_parses_pace_fields_and_normalises_dates(self):
        obj = MayoObject.parse(
            {
                "_source_layer": "pace",
                "FID": 1,
                "FileNumber": "0015",
                "RECEIVED": "05/01/2000",
                "DECDATE": " ",
                "APP_STATUS": 2,
                "APP_TYPE": "O",
                "DESCRIPT": "CONSTRUCT DWELLINGS",
                "DEV_ADD1": "CLOONAWEEMA",
                "DEV_ADD2": "CHARLESTOWN",
                "DECISION": "R",
                "iPlan_Link": "https://example.test/0015",
            }
        )
        self.assertEqual(obj.application_number, "0015")
        self.assertEqual(obj.address, "CLOONAWEEMA, CHARLESTOWN")
        self.assertEqual(obj.received_date, 947030400000)
        self.assertIsNone(obj.decision_date)
        self.assertEqual(obj.source_layer, "pace")

    def test_louth_object_parses_arcgis_fields(self):
        louth_db.recreate()
        LouthObject.parse(
            {
                "FID": 1,
                "FileRef": "03510263",
                "AppName": "Jons Civil Eng.",
                "RedDate": "20031119000000",
                "Dec_date": "22/01/2004",
                "MO_Dec_Dat": "20040122000000",
                "Loc": "NORTH BANK",
                "AllDevAdd": "Haymarket Building   NORTH BANK",
                "DevDesc": "Change of use",
                "Decision": "CONDITIONAL",
                "AppStatus": "APPLICATION FINALISED",
                "FileNo": 510263,
                "Year": "03",
                "GlobalID": "test-global-id",
                "CreationDate_2": 1779878032582,
                "EditDate_2": 1779878032582,
                "Shape__Area": 17037.7,
                "Shape__Length": 927.4,
            }
        ).save()
        saved = LouthObject.get_by_id(1)
        self.assertEqual(LouthObject._meta.database.database, LOUTH_DB_LOCATION)
        self.assertEqual(saved.application_number, "03510263")
        self.assertEqual(saved.address, "Haymarket Building NORTH BANK")
        self.assertEqual(saved.received_date, "20031119000000")
        self.assertEqual(saved.decision_date, "22/01/2004")

    def test_wicklow_object_parses_arcgis_fields_and_corrects_coordinates(self):
        wicklow_db.recreate()
        WicklowObject.parse(
            {
                "OBJECTID": 1,
                "file_number": "883585",
                "forename": "Kevin ",
                "surname": "Doran",
                "decision_code": "U",
                "STATUS": "Grant",
                "status_desc": "Application Finalised",
                "dev_address_line1": "Golden Hill, Manor",
                "dev_address_line2": "Kilbride",
                "dev_address_line3": "",
                "development_descri": "Extension to dwelling",
                "received_date": 570844800000,
                "decision_date": 573350400000,
                "Link2ePlan": "http://example.test/883585",
                "Lat": -6.47750931,
                "Long": 53.20335191,
                "ApplicationType": "Permission",
            }
        ).save()
        saved = WicklowObject.get_by_id(1)
        self.assertEqual(WicklowObject._meta.database.database, WICKLOW_DB_LOCATION)
        self.assertEqual(saved.application_number, "883585")
        self.assertEqual(saved.applicant_name, "Kevin Doran")
        self.assertEqual(saved.address, "Golden Hill, Manor, Kilbride")
        self.assertEqual(saved.latitude, 53.20335191)
        self.assertEqual(saved.longitude, -6.47750931)

    def test_kerry_object_parses_arcgis_fields(self):
        kerry_db.recreate()
        prefix = "arcgis_sde_PES_Points_and_iPLAN_All_PlanDB_"
        KerryObject.parse(
            {
                "OBJECTID": 1,
                "PaceDL_FileNumber": "071",
                "PaceDL_ReceivedDate": 1167696000000,
                "PaceDL_created_date": 1646840223000,
                f"{prefix}Planning_Number": "071",
                f"{prefix}Applicant_Name": "COLETTE HENDRICK",
                f"{prefix}Development_Address": "COOL EAST VALENTIA   COOL EAST ",
                f"{prefix}Date_Received": "2007-01-02",
                f"{prefix}Decision_Due_Date": "2007-02-26",
                f"{prefix}Decision": "REFUSED",
                f"{prefix}Decision_Date_MO": "2007-02-21",
                f"{prefix}Application_Status": "APPLICATION FINALISED",
                f"{prefix}Development_Descripti": "ERECT A DWELLINGHOUSE",
                "Shape__Area": 7380.278,
                "Shape__Length": 373.4,
            }
        ).save()

        saved = KerryObject.get_by_id(1)
        self.assertEqual(KerryObject._meta.database.database, KERRY_DB_LOCATION)
        self.assertEqual(saved.application_number, "071")
        self.assertEqual(saved.address, "COOL EAST VALENTIA COOL EAST")
        self.assertEqual(saved.received_date, "2007-01-02")
        self.assertEqual(saved.pace_received_date, 1167696000000)
        self.assertEqual(saved.applicant_name, "COLETTE HENDRICK")

    def test_wexford_object_parses_arcgis_fields(self):
        wexford_db.recreate()
        WexfordObject.parse(
            {
                "OBJECTID": 1,
                "Address": "'ROS RUA', BALLYGARRETT, CO. WEXFORD",
                "Planning_Number": "941743",
                "Thematic_Decision": "Granted",
                "DirectLink2DMS": "https://example.test/wexford/10589",
                "Description": "ERECTION OF A DOUBLE GARAGE",
            },
            {
                "ApplicationNumber": "941743",
                "ApplicationType": "PERMISSION",
                "ApplicationStatus": "Application Finalised",
                "DecisionDate": 778204800000,
            },
            {
                "Planning_Number": "941743",
                "Reg_date": 773020800000,
            },
        ).save()

        saved = WexfordObject.get_by_id(1)
        self.assertEqual(WexfordObject._meta.database.database, WEXFORD_DB_LOCATION)
        self.assertEqual(saved.objid, 1)
        self.assertEqual(saved.application_number, "941743")
        self.assertEqual(saved.decision, "Granted")
        self.assertEqual(saved.received_date, 773020800000)
        self.assertEqual(saved.decision_date, 778204800000)
        self.assertEqual(saved.address, "'ROS RUA', BALLYGARRETT, CO. WEXFORD")
        self.assertEqual(saved.details_url, "https://example.test/wexford/10589")

    def test_wexford_parses_agile_application_dates(self):
        self.assertEqual(
            _wexford_application_id(
                "https://planning.agileapplications.ie/wexford/application-details/10589"
            ),
            "10589",
        )
        self.assertEqual(
            _parse_wexford_dates(
                {
                    "receivedDate": "1994-12-19T00:00:00",
                    "registrationDate": "1994-12-20T00:00:00",
                    "decisionDate": "1995-02-03T00:00:00Z",
                }
            ),
            {
                "ReceivedDate": 787795200000,
                "DecisionDate": 791769600000,
            },
        )

    def test_donegal_object_normalises_modern_arcgis_fields(self):
        donegal_db.recreate()
        DonegalObject.parse(
            {
                "_source_layer": "since_2010",
                "OBJECTID": 1,
                "FILE_NUMBE": "1010000",
                "received_d": "06/01/2010",
                "decision_d": "02/03/2010",
                "developmen": "Permission for a coffee shop",
                "location_k": "DRUMACRIN",
                "decision00": "Permission for development",
                "ApplicName": "Anne Marie & Karen Fitzgerald",
                "decision_c": "CONDITIONAL",
                "Applicatio": "Finalised",
                "DEC_CODE": "Granted",
                "ePlanLink": "https://example.test/eplan/1010000",
                "linkpcdoc": "https://example.test/docs/1010000",
            }
        ).save()

        saved = DonegalObject.get_by_id(1)
        self.assertEqual(DonegalObject._meta.database.database, DONEGAL_DB_LOCATION)
        self.assertEqual(saved.application_number, "1010000")
        self.assertEqual(saved.address, "DRUMACRIN")
        self.assertEqual(saved.received_date, "06/01/2010")
        self.assertEqual(saved.application_status, "Finalised")
        self.assertEqual(saved.source_layer, "since_2010")

    def test_donegal_object_normalises_historical_arcgis_fields(self):
        donegal_db.recreate()
        obj = DonegalObject.parse(
            {
                "_source_layer": "2000_2004",
                "OBJECTID": 161328,
                "FILE_NUMBER": "042336",
                "received_date": 1077235200000,
                "decision_date": 1088467200000,
                "development_descri": "TEACH CONAI",
                "location_key": "GHLASAIGH",
                "ApplicationStatus": "Finalised",
                "decision_description": "TEACH CONAI A THOGAIL",
                "ApplicName": "CAITLIN GAVIN",
                "DEC_CODE": "Granted",
            }
        )
        self.assertEqual(obj.application_number, "042336")
        self.assertEqual(obj.received_date, 1077235200000)
        self.assertEqual(obj.description, "TEACH CONAI")

    def test_tipperary_object_parses_arcgis_fields(self):
        tipperary_db.recreate()
        TipperaryObject.parse(
            {
                "OBJECTID": 1,
                "FileNumber": "001302",
                "ApplicationType": None,
                "ePlan_Link": "http://example.test/001302",
                "decision_date": 998352000000,
                "application_status": "APPLICATION FINALISED",
                "surname": "Hennessey",
                "forename": "Caroline",
                "development_descri": "construction of a dwelling",
                "decision_m_o_date": 997228800000,
                "application_type": "OUTLINE PERMISSION",
                "DECISION": "REFUSED",
                "location_key": "BALLINAHALLA",
                "Appeal_Date": None,
                "Appeal_Decision": None,
                "protected_struct_flag": None,
                "part_5_flag": None,
                "section_47_flag": None,
                "GlobalID": "ee8dfca0-bbc0-45ad-9fa4-709d5e0acdc0",
                "GoogleMaps_Link": "https://maps.example.test/location",
                "StreetView_Link": "https://maps.example.test/street-view",
                "Status": "REFUSED",
            },
            {
                "ApplicationNumber": "001302",
                "ReceivedDate": 993945600000,
                "DecisionDate": 998352000000,
            },
        ).save()

        saved = TipperaryObject.get_by_id(1)
        self.assertEqual(TipperaryObject._meta.database.database, TIPPERARY_DB_LOCATION)
        self.assertEqual(saved.application_number, "001302")
        self.assertEqual(saved.applicant_name, "Caroline Hennessey")
        self.assertEqual(saved.address, "BALLINAHALLA")
        self.assertEqual(saved.application_type, "OUTLINE PERMISSION")
        self.assertEqual(saved.received_date, 993945600000)
        self.assertEqual(saved.decision_date, 998352000000)

    def test_limerick_object_decodes_azimap_fields(self):
        limerick_db.recreate()
        LimerickObject.parse(
            {
                "geom": "",
                "file_number": "001",
                "siteid": "0",
                "year": "2000",
                "decision": "CONDITIONAL",
                "type": "PERMISSION",
                "status": "APPLICATION%20FINALISED",
                "description": "Construction%20of%20a%20dwelling%20%26%20garage",
                "applicant_full_name": "Kevin%20%26%20Denise%20Brown",
                "development_address": "Glenmore%20East%2C%20Strand%20%20",
                "cso_category": "",
                "cso_category_description": "",
                "area": "",
                "unit_of_measure": "",
                "unit_description": "",
                "unit_number": "",
            },
            {
                "ApplicationNumber": "001",
                "ReceivedDate": 946684800000,
                "DecisionDate": 951868800000,
            },
        ).save()

        saved = LimerickObject.get_by_id(1)
        self.assertEqual(LimerickObject._meta.database.database, LIMERICK_DB_LOCATION)
        self.assertEqual(saved.application_number, "001")
        self.assertEqual(saved.application_status, "APPLICATION FINALISED")
        self.assertEqual(saved.received_date, 946684800000)
        self.assertEqual(saved.decision_date, 951868800000)
        self.assertEqual(saved.applicant_name, "Kevin & Denise Brown")
        self.assertEqual(saved.address, "Glenmore East, Strand")
        self.assertEqual(saved.year, 2000)

    def test_meath_object_parses_arcgis_fields(self):
        meath_db.recreate()

        MeathObject.parse(
            {
                "OBJECTID": 2,
                "PlanningAuthority": "Meath County Council",
                "PlanningReference": "0010",
                "Decision": "Pending or Withdrawn",
                "RecievedDate": 947116800000,
                "DecisionDate": 959472000000,
                "Applicant": "Patrick Smullen",
                "ApplicationStatus": "Withdrawn",
                "DevelopmentDescription": "Alter & extend dwelling",
                "Address_Line1": "Ticroghan",
                "Address_Line2": "Clonard",
                "Address_Line3": "Co Meath",
                "LinktoScannedDocuments": "http://example.test/documents/0010",
                "LinktoePlan": "http://example.test/planning/0010",
                "GlobalID": "bc01aecb-7c7e-4eaf-ab4d-b75c603f0e8a",
            }
        ).save()

        saved = MeathObject.get(MeathObject.application_number == "0010")

        self.assertEqual(MeathObject._meta.database.database, MEATH_DB_LOCATION)
        self.assertEqual(saved.objid, 2)
        self.assertEqual(saved.address, "Ticroghan, Clonard, Co Meath")
        self.assertEqual(saved.received_date, 947116800000)
        self.assertEqual(saved.decision_date, 959472000000)
        self.assertEqual(saved.applicant_name, "Patrick Smullen")
        self.assertEqual(saved.description, "Alter & extend dwelling")
        self.assertEqual(saved.link_eplanning, "http://example.test/planning/0010")
        self.assertEqual(saved.global_id, "bc01aecb-7c7e-4eaf-ab4d-b75c603f0e8a")

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
