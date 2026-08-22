import time
import json
from typing import Iterable, List

import progressbar
import requests
from peewee import (
    Model,
    TextField,
    IntegerField,
    CharField,
    FloatField,
    SqliteDatabase,
    IntegrityError,
)

from planning_permission.settings import CORK_DB_LOCATION, SLEEP_BETWEEN_REQUESTS
from planning_permission.utils import clean_address_for_comparison, write_to_db

CORK_CITY_URL = (
    "https://services-eu1.arcgis.com/f0ZQOHXBIeLonX0V/arcgis/rest/services/"
    "PlanningPolygon_2_view/FeatureServer/0/query"
)
CORK_COUNTY_URL = (
    "https://services.arcgis.com/NzlPQPKn5QF9v2US/arcgis/rest/services/"
    "IrishPlanningApplications/FeatureServer/0/query"
)
CORK_COUNTY_WHERE = "PlanningAuthority = 'Cork County Council'"
CORK_CITY_FIRST_YEAR = 1999
CORK_CITY_LAST_YEAR = 2026
CORK_CITY_PAGE_SIZE = 1000
CORK_COUNTY_PAGE_SIZE = 2000
CORK_REQUEST_TIMEOUT = 60
CORK_SPATIAL_REFERENCE = 2157
CORK_CITY_YEAR_FILTERS = (
    f"FileYear < {CORK_CITY_FIRST_YEAR} OR FileYear IS NULL",
    *(
        f"FileYear = {year}"
        for year in range(CORK_CITY_FIRST_YEAR, CORK_CITY_LAST_YEAR + 1)
    ),
)


def download_cork():
    objects = []

    for where in progressbar.progressbar(CORK_CITY_YEAR_FILTERS, prefix="Cork City: "):
        features = []
        offset = 0
        while True:
            response = requests.get(
                CORK_CITY_URL,
                params={
                    "f": "json",
                    "where": where,
                    "returnGeometry": "true",
                    "spatialRel": "esriSpatialRelIntersects",
                    "outFields": "*",
                    "outSR": CORK_SPATIAL_REFERENCE,
                    "orderByFields": "OBJECTID ASC",
                    "resultOffset": offset,
                    "resultRecordCount": CORK_CITY_PAGE_SIZE,
                },
                headers={},
                timeout=CORK_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            page = data.get("features", [])
            features.extend(page)
            offset += len(page)
            if not page or data.get("exceededTransferLimit") is False:
                break

        for item in features:
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
            objects.append(CorkObject.parse(parsed_dict))

    count_response = requests.get(
        CORK_COUNTY_URL,
        params={
            "f": "json",
            "where": CORK_COUNTY_WHERE,
            "returnCountOnly": "true",
        },
        timeout=CORK_REQUEST_TIMEOUT,
    )
    count_response.raise_for_status()
    county_total = count_response.json()["count"]
    county_bar = progressbar.ProgressBar(
        max_value=county_total,
        prefix="Cork County: ",
    )
    county_bar.start()

    offset = 0
    while True:
        response = requests.get(
            CORK_COUNTY_URL,
            params={
                "f": "json",
                "where": CORK_COUNTY_WHERE,
                "returnGeometry": "false",
                "outFields": "*",
                "orderByFields": "OBJECTID ASC",
                "resultOffset": offset,
                "resultRecordCount": CORK_COUNTY_PAGE_SIZE,
            },
            timeout=CORK_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        page = data.get("features", [])
        for item in page:
            attrs = item["attributes"]
            applicant_name = " ".join(
                value.strip()
                for value in (
                    attrs.get("ApplicantForename"),
                    attrs.get("ApplicantSurname"),
                )
                if value and value.strip()
            )
            objects.append(
                CorkObject.parse(
                    {
                        "address": attrs.get("DevelopmentAddress") or "",
                        "objid": attrs.get("OBJECTID"),
                        "planning_authority": attrs.get("PlanningAuthority"),
                        "applicant_name": applicant_name or None,
                        "application_number": attrs.get("ApplicationNumber"),
                        "received_date": attrs.get("ReceivedDate"),
                        "link_app_details": attrs.get("LinkAppDetails"),
                        "application_type": attrs.get("ApplicationType"),
                        "description": attrs.get("DevelopmentDescription"),
                        "development_address": attrs.get("DevelopmentAddress"),
                        "decision": attrs.get("Decision"),
                        "application_status": attrs.get("ApplicationStatus"),
                        "site_area": attrs.get("AreaofSite"),
                        "withdrawn_date": attrs.get("WithdrawnDate"),
                        "decision_due_date": attrs.get("DecisionDueDate"),
                        "decision_date": attrs.get("DecisionDate"),
                        "grant_date": attrs.get("GrantDate"),
                        "expiry_date": attrs.get("ExpiryDate"),
                        "appeal_ref_number": attrs.get("AppealRefNumber"),
                        "appeal_submitted_date": attrs.get("AppealSubmittedDate"),
                        "appeal_decision": attrs.get("AppealDecision"),
                        "appeal_decision_date": attrs.get("AppealDecisionDate"),
                        "fi_request_date": attrs.get("FIRequestDate"),
                        "fi_received_date": attrs.get("FIRecDate"),
                    }
                )
            )
        offset += len(page)
        county_bar.update(min(offset, county_total))
        if not page or data.get("exceededTransferLimit") is False:
            break
        time.sleep(SLEEP_BETWEEN_REQUESTS)
    county_bar.finish()

    write_to_db(cork_db, CorkObject, objects)


class CorkObject(Model):
    objid = IntegerField(null=True)
    address = CharField()
    searchable_address = CharField()

    planning_authority = CharField(null=True)
    applicant_name = CharField(null=True)
    application_number = CharField(null=True)
    application_type = CharField(null=True)
    application_status = CharField(null=True)
    description = TextField(null=True)
    development_address = TextField(null=True)
    decision = CharField(null=True)
    site_area = CharField(null=True)

    received_date = CharField(null=True)
    withdrawn_date = CharField(null=True)
    decision_due_date = CharField(null=True)
    decision_date = CharField(null=True)
    grant_date = CharField(null=True)
    expiry_date = CharField(null=True)
    appeal_submitted_date = CharField(null=True)
    appeal_decision_date = CharField(null=True)
    fi_request_date = CharField(null=True)
    fi_received_date = CharField(null=True)
    submission_date = CharField(null=True)

    file_year = IntegerField(null=True)
    appeal_ref_number = CharField(null=True)
    appeal_decision = CharField(null=True)
    appeal_type = CharField(null=True)
    fi_file_number = CharField(null=True)
    num_house_dev = IntegerField(null=True)
    number_floors = IntegerField(null=True)
    number_conditions = IntegerField(null=True)

    link_app_details = CharField(null=True)
    link_docs = CharField(null=True)
    link_docs_internal = CharField(null=True)
    global_id = CharField(null=True)
    shape_area = FloatField(null=True)
    shape_length = FloatField(null=True)
    geometry = TextField(null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.address = self.address.strip().replace(" ,", ",")
        while "  " in self.address:
            self.address = self.address.replace("  ", " ")

        if not self.searchable_address:
            self.searchable_address = self.compute_searchable_address()

    class Meta:
        database = SqliteDatabase(CORK_DB_LOCATION)

    def save(self, *args, **kwargs):
        self.searchable_address = self.compute_searchable_address()
        try:
            return super(CorkObject, self).save(*args, **kwargs)
        except IntegrityError:
            pass

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return f"{self.application_number or self.objid}: {self.address}"

    def compute_searchable_address(self) -> str:
        return clean_address_for_comparison(self.address)

    @staticmethod
    def parse(data):
        if isinstance(data, CorkObject):
            return data
        if isinstance(data, dict):
            data.pop(None, None)
        return CorkObject(**data)


class CorkDB:
    def __init__(self) -> None:
        self.create_connection()

    def __len__(self) -> int:
        return CorkObject.select().count()

    def __iter__(self) -> Iterable[CorkObject]:
        return CorkObject.select().iterator()

    def drop_data(self) -> None:
        CorkObject.delete().execute()

    def recreate(self) -> None:
        self.db.drop_tables([CorkObject], safe=True)
        self.db.create_tables([CorkObject])

    def create_connection(self) -> None:
        self.db = SqliteDatabase(CORK_DB_LOCATION)
        self.db.connect()
        self.db.create_tables([CorkObject])

    def close(self):
        self.db.close()

    def filter(
        self,
        address_substrs=None,
        exclude_address_substrs=None,
        address=None,
        county=None,
        eircode=None,
        eircode_routing_key=None,
        partial: bool = False,
    ) -> List[CorkObject]:
        filters = {}

        query = CorkObject.select()

        for field, value in filters.items():
            if value is not None:
                field_name = getattr(CorkObject, field)
                if partial:
                    query = query.where(field_name.ilike(f"%{value}%"))
                else:
                    query = query.where(field_name.ilike(value))

        if address:
            address = address.replace(" ", "").replace(",", "").lower()
            if partial:
                query = query.where(CorkObject.searchable_address.contains(address))
            else:
                query = query.where(CorkObject.searchable_address == address)

        if address_substrs:
            for address_substr in address_substrs:
                query = query.where(
                    CorkObject.searchable_address.contains(
                        clean_address_for_comparison(address_substr)
                    )
                )

        if exclude_address_substrs:
            for exclude_address_substr in exclude_address_substrs:
                query = query.where(
                    ~(
                        CorkObject.searchable_address.contains(
                            clean_address_for_comparison(exclude_address_substr)
                        )
                    )
                )

        return [obj for obj in query]


cork_db = CorkDB()
