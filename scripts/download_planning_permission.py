import json
import string
import os
import math
from time import sleep
from datetime import datetime

import backoff
import requests
import progressbar
from peewee import chunked

from planning_permission.settings import (
    PLANNING_PERMISSION_LOCATION,
    DCC_SAVES_LOCATION,
    SLEEP_BETWEEN_REQUESTS,
)

from planning_permission.planning_permission_db import (
    PlanningPermissionObject,
    planning_permission_db,
)
from planning_permission.dcc import DCCObject, dcc_db
from planning_permission.cork import CorkObject, cork_db
from planning_permission.galway import GalwayObject, galway_db
from planning_permission.kildare import KildareObject, kildare_db
from planning_permission.utils import (
    normalise,
    read_json,
    download_planning_permission,
    itm_to_lat_lng,
    web_mercator_to_lat_lng,
)

FIELD_MAP = {
    "PlanningAuthority": "planning_authority",
    "ApplicationNumber": "application_number",
    "DevelopmentDescription": "development_description",
    "DevelopmentAddress": "development_address",
    "DevelopmentPostcode": "development_postcode",
    "ApplicationStatus": "application_status",
    "ApplicationType": "application_type",
    "ApplicantForename": "applicant_forename",
    "ApplicantSurname": "applicant_surname",
    "ApplicantAddress": "applicant_address",
    "Decision": "decision",
    "LandUseCode": "land_use_code",
    "AreaofSite": "area_of_site",
    "NumResidentialUnits": "num_residential_units",
    "OneOffHouse": "one_off_house",
    "FloorArea": "floor_area",
    "ReceivedDate": "received_date",
    "WithdrawnDate": "withdrawn_date",
    "DecisionDate": "decision_date",
    "DecisionDueDate": "decision_due_date",
    "GrantDate": "grant_date",
    "ExpiryDate": "expiry_date",
    "AppealRefNumber": "appeal_ref_number",
    "AppealStatus": "appeal_status",
    "AppealDecision": "appeal_decision",
    "AppealDecisionDate": "appeal_decision_date",
    "AppealSubmittedDate": "appeal_submitted_date",
    "FIRequestDate": "fi_request_date",
    "FIRecDate": "fi_rec_date",
    "LinkAppDetails": "link_app_details",
    "OneOffKPI": "one_off_kpi",
    "ETL_DATE": "etl_date",
    "SiteId": "site_id",
    "ORIG_FID": "orig_fid",
}

DCC_FIELD_MAP = {
    "id": "objid",
    "location": "address",
    "proposal": "proposal",
    "applicantSurname": "applicant_surname",
    "applicantPropKey": "applicant_prop_key",
    "registrationDate": "registration_date",
    "decisionDate": "decision_date",
    "decisionText": "decision_text",
    "finalGrantDate": "final_grant_date",
    "extensionDate": "extension_date",
    "appealLodgedDate": "appeal_lodged_date",
    "appealDecisionDate": "appeal_decision_date",
    "appealNotifyDate": "appeal_notify_date",
    "abpReference": "abp_reference",
    "appealDecision": "appeal_decision",
    "postcode": "postcode",
    "fullProposal": "full_proposal",
    "registerDate": "register_date",
    "dispatchDate": "dispatch_date",
    "statusDescription": "status_description",
    "statusOwner": "status_owner",
    "statusNonOwner": "status_non_owner",
    "applicationTypeId": "application_type_id",
    "applicationType": "application_type",
    "statutoryExpiryDate": "statutory_expiry_date",
    "decisionExpiryDate": "decision_expiry_date",
    "agentSurname": "agent_surname",
    "officerName": "officer_name",
    "appealType": "appeal_type",
    "receivedDate": "received_date",
    "commentsMode": "comments_mode",
    "publicityEndDate": "publicity_end_date",
    "submissionExpiryDate": "submission_expiry_date",
    "applicationDate": "application_date",
    "decisionDueDate": "decision_due_date",
    "uprn": "uprn",
    "agentPropKey": "agent_prop_key",
    "propertyId": "property_id",
}

DCC_DATE_FIELDS = {
    "registration_date",
    "decision_date",
    "final_grant_date",
    "extension_date",
    "appeal_lodged_date",
    "appeal_decision_date",
    "appeal_notify_date",
    "register_date",
    "dispatch_date",
    "statutory_expiry_date",
    "decision_expiry_date",
    "received_date",
    "publicity_end_date",
    "submission_expiry_date",
    "application_date",
    "decision_due_date",
}


@backoff.on_exception(
    backoff.expo, (requests.exceptions.RequestException,), max_tries=5
)
def get(url, headers=None):
    sleep(SLEEP_BETWEEN_REQUESTS)
    response = requests.get(url, headers=headers)
    if response.status_code == 404:
        return response
    else:
        response.raise_for_status()
    return response


def download_cork():
    cork_db.recreate()

    for year in progressbar.progressbar(range(1999, 2027)):
        url = "https://services-eu1.arcgis.com/f0ZQOHXBIeLonX0V/arcgis/rest/services/PlanningPolygon_2_view/FeatureServer/0/query"

        params = {
            "f": "json",
            "where": f"FileYear = {year}",
            "returnGeometry": "true",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "outSR": 2157,
            "resultOffset": 0,
            "resultRecordCount": 100000,
        }

        response = requests.get(
            url,
            params=params,
            headers={},
            timeout=60,
        )

        response.raise_for_status()

        data = response.json()

        for item in data["features"]:
            attrs = item["attributes"]

            parsed_dict = {
                "address": attrs.get("ApplicantAddress")
                or attrs.get("DevelopmentAddress")
                or "",
                "objid": attrs.get("OBJECTID"),
                "planning_authority": attrs.get("PlanningAuthority"),
                "applicant_name": attrs.get("ApplicantName"),
                "application_number": attrs.get("PlanningApReference"),
                "received_date": attrs.get("DateReceiptAp"),
                "link_app_details": attrs.get("LinkAppDetails"),
                "link_docs": attrs.get("LinkDocs"),
                "application_type": attrs.get("ApplicationType"),
                "description": attrs.get("DevDescription"),
                "development_address": attrs.get("DevelopmentAddress"),
                "decision": attrs.get("Decision"),
                "application_status": attrs.get("ApplicationStatus"),
                "site_area": attrs.get("SiteArea"),
                "withdrawn_date": attrs.get("WithdrawnDate"),
                "decision_due_date": attrs.get("DecisionDueDate"),
                "decision_date": attrs.get("DecisonDate"),
                "grant_date": attrs.get("GrantDate"),
                "expiry_date": attrs.get("ExpiryDate"),
                "file_year": attrs.get("FileYear"),
                "appeal_ref_number": attrs.get("AppealRefNumber"),
                "appeal_submitted_date": attrs.get("DateAppealSubmitted"),
                "appeal_decision": attrs.get("AppealDecision"),
                "appeal_decision_date": attrs.get("DateAppealDecision"),
                "appeal_type": attrs.get("appealType"),
                "fi_file_number": attrs.get("FIFileNumber"),
                "fi_request_date": attrs.get("FIRequestDate"),
                "fi_received_date": attrs.get("FIReceivedDate"),
                "submission_date": attrs.get("SubmissionDate"),
                "num_house_dev": attrs.get("NumHouseDev"),
                "number_floors": attrs.get("NumberFloors"),
                "number_conditions": attrs.get("NumberConditions"),
                "link_docs_internal": attrs.get("LinkDocsInternal"),
                "global_id": attrs.get("GlobalID"),
                "shape_area": attrs.get("Shape__Area"),
                "shape_length": attrs.get("Shape__Length"),
                "geometry": json.dumps(item.get("geometry")),
            }
            cork_obj = CorkObject.parse(parsed_dict)
            cork_obj.save()


def parse_dcc_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()

    for date_format in (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%a, %d %b %Y %H:%M:%S GMT",
    ):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            pass

    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def parse_dcc_application(data):
    if data.get("status_code") == 404:
        return None

    props = {}
    for old, new in DCC_FIELD_MAP.items():
        value = data.get(old)
        if new in DCC_DATE_FIELDS:
            value = parse_dcc_date(value)
        props[new] = value

    props["lat"], props["lng"] = itm_to_lat_lng(
        data.get("easting"),
        data.get("northing"),
    )

    if not props["objid"] or not props["address"]:
        return None

    return DCCObject.parse(props)


def save_dcc_application(data):
    obj = parse_dcc_application(data)
    if obj:
        obj.save()


def download_dublin():
    print("Downloading Dublin")

    headers = {
        "Accept": "application/json, text/plain, */*",
        "x-client": "DCC",  # Can we just change this for other cities?
        "x-product": "CITIZENPORTAL",
        "x-service": "PA",
    }

    # counter = 0
    # for objid in progressbar.progressbar(range(1, 200_000)):
    #    fp = os.path.join(DCC_SAVES_LOCATION, str(objid))
    #    data = None
    #    with open(fp) as fh:
    #        data = json.loads(fh.read())
    #    if data.get('status_code') == 404:
    #        counter += 1
    #    else:
    #        counter = 0
    #    if counter > 70:
    #        print(counter)
    # return

    for objid in progressbar.progressbar(list(reversed(range(1, 200_000)))):
        fp = os.path.join(DCC_SAVES_LOCATION, str(objid))
        if not os.path.exists(fp):
            continue
        data = None
        with open(fp) as fh:
            data = json.loads(fh.read())
        if data.get("status_code") == 404:
            os.remove(fp)
        else:
            break

    dcc_db.recreate()

    not_found_counter = 0

    for objid in progressbar.progressbar(range(1, 200_000)):
        save_path = os.path.join(DCC_SAVES_LOCATION, str(objid))

        if os.path.exists(save_path):
            with open(save_path) as fh:
                save_dcc_application(json.loads(fh.read()))
            continue

        url = f"https://planningapi.agileapplications.ie/api/application/{objid}"
        response = get(url, headers=headers)

        if response.status_code == 404:
            with open(save_path, "w") as fh:
                fh.write(json.dumps({"status_code": 404}))
            not_found_counter += 1
            if not_found_counter >= 100:
                break
        else:
            not_found_counter = 0
            data = response.json()
            with open(save_path, "w") as fh:
                fh.write(json.dumps(data))

            save_dcc_application(data)


def download_base():
    print("Downloading geojson")
    download_planning_permission()

    planning_permission_db.drop_data()

    objects = []

    print("Parsing data...")
    for planning_permission_dict in progressbar.progressbar(
        read_json(PLANNING_PERMISSION_LOCATION)["features"]
    ):
        props = normalise(planning_permission_dict["properties"], FIELD_MAP)
        coords = planning_permission_dict["geometry"]["coordinates"]
        props["lat"], props["lng"] = web_mercator_to_lat_lng(coords[0], coords[1])
        objects.append(PlanningPermissionObject.parse(props))

    batch_size = 500
    total_batches = math.ceil(len(objects) / batch_size)
    print(f"Inserting chunks of size {batch_size} to db...")

    with planning_permission_db.db.atomic():
        for batch in progressbar.progressbar(
            chunked(objects, batch_size),
            max_value=total_batches,
        ):
            PlanningPermissionObject.bulk_create(batch, batch_size=batch_size)


def download_galway():
    print("Downloading Galway")

    url = "https://services1.arcgis.com/mJI7JYqAOKXPG7Hh/arcgis/rest/services/GCC_PlanningRegisterPts_16/FeatureServer/2/query"

    galway_db.recreate()

    request_count = 0
    more = True
    while more:
        per_page = 1000

        params = {
            "f": "json",
            "where": "1=1",
            "returnGeometry": "true",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "resultOffset": per_page * request_count,
            "resultRecordCount": per_page,
        }

        response = requests.get(
            url,
            params=params,
            headers={},
            timeout=60,
        )

        response.raise_for_status()

        data = response.json()

        if not data["features"]:
            more = False

        for item in data["features"]:
            attrs = item["attributes"]
            lat, lng = itm_to_lat_lng(
                attrs.get("ITMEasting"),
                attrs.get("ITMNorthing"),
            )

            parsed_dict = {
                "address": attrs["Location"],
                "objid": attrs["OBJECTID"],
                "application_number": attrs["ApplicationNumber"],
                "applicant_name": attrs["ApplicantName"],
                "received_date": attrs["ReceivedDate"],
                "application_type": attrs["ApplicationType"],
                "application_status": attrs["ApplicationStatus"],
                "description": attrs["Description"],
                "decision": attrs["Decision"],
                "decision_date": attrs["DecisionDate"],
                "decision_due_date": attrs["DecisionDueDate"],
                "withdrawn_date": attrs.get("WithdrawnDate"),
                "grant_date": attrs.get("GrantDate"),
                "expiry_date": attrs.get("ExpiryDate"),
                "appeal_notification_date": attrs.get("AppealNotificationDate"),
                "appeal_ref_num": attrs.get("AppealRefNum"),
                "appeal_decision": attrs.get("AppealDecision"),
                "appeal_decision_date": attrs.get("AppealDecisionDate"),
                "lat": lat,
                "lng": lng,
                "more_info": attrs.get("MoreInfo"),
                "global_id": attrs.get("GlobalID"),
            }

            galway_obj = GalwayObject.parse(parsed_dict)
            galway_obj.save()

        request_count += 1


def download_kildare():
    print("Downloading Kildare")

    base_url = "https://webgeo.kildarecoco.ie/planningenquiry/Public/GetPlanningFileNameAddressResult?name=&address={letter}&devDesc=&startDate=&endDate="

    kildare_db.drop_data()

    objects = []
    application_numbers = set()
    for letter in progressbar.progressbar(list(reversed(string.ascii_lowercase))):
        url = base_url.format(letter=letter)

        response = get(url)

        for obj_dict in response.json():
            obj = KildareObject.parse(obj_dict)
            if obj.application_number not in application_numbers:
                objects.append(obj)
                application_numbers.add(obj.application_number)

    batch_size = 500
    total_batches = math.ceil(len(objects) / batch_size)
    print(f"Inserting chunks of size {batch_size} to db...")

    with kildare_db.db.atomic():
        for batch in progressbar.progressbar(
            chunked(objects, batch_size),
            max_value=total_batches,
        ):
            KildareObject.bulk_create(batch, batch_size=batch_size)


def main():
    download_base()
    download_dublin()
    download_cork()
    download_galway()
    download_kildare()


if __name__ == "__main__":
    main()
