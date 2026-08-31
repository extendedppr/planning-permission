import re
import threading
import time
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Iterable, List

import progressbar
import requests
from bs4 import BeautifulSoup
from peewee import CharField, FloatField, IntegerField, Model, SqliteDatabase, TextField

from planning_permission.settings import MAYO_DB_LOCATION
from planning_permission.utils import clean_address_for_comparison, write_to_db


mayo_database = SqliteDatabase(MAYO_DB_LOCATION)
MAYO_URL = "https://services.arcgis.com/NzlPQPKn5QF9v2US/arcgis/rest/services/IrishPlanningApplications/FeatureServer/1/query"
MAYO_WHERE = "PlanningAuthority = 'Mayo County Council'"
MAYO_BASE_URL = "https://www.eplanning.ie"
MAYO_DETAIL_URL = f"{MAYO_BASE_URL}/MayoCC/AppFileRefDetails/{{}}/0"
MAYO_REQUEST_ATTEMPTS = 6
MAYO_REQUEST_WORKERS = 10
MAYO_INDEX_LAYERS = (
    (
        "historical",
        "https://services6.arcgis.com/Pd1cyjBoR66OI0XF/arcgis/rest/services/HIstorical_Planning/FeatureServer/1/query",
        "1=1",
        "file_number",
    ),
    (
        "pace",
        "https://services6.arcgis.com/Pd1cyjBoR66OI0XF/arcgis/rest/services/PACE_MayoSites/FeatureServer/0/query",
        "1=1",
        "FileNumber",
    ),
    ("national", MAYO_URL, MAYO_WHERE, "ApplicationNumber"),
)
MAYO_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
}


def _is_missing_mayo_detail(response):
    return (
        "/MayoCC/AppFileRefDetails/" in response.url
        and "ePlan server is experiencing a problem" in response.text
        and "Full technical details of this error" in response.text
    )


def _mayo_request(session, method, url, **kwargs):
    for attempt in range(MAYO_REQUEST_ATTEMPTS):
        try:
            response = session.request(
                method,
                url,
                headers=MAYO_HEADERS,
                timeout=120,
                **kwargs,
            )
            if _is_missing_mayo_detail(response):
                return response
            if response.status_code == 429 or response.status_code >= 500:
                response.raise_for_status()
            return response
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError):
            if attempt == MAYO_REQUEST_ATTEMPTS - 1:
                raise
            time.sleep(2**attempt)


def _detail_fields(section):
    fields = {}
    if section is None:
        return fields
    for row in section.select("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        for index, cell in enumerate(cells[:-1]):
            if cell.name == "th" and cells[index + 1].name == "td":
                label = " ".join(cell.get_text(" ", strip=True).rstrip(":").split())
                value = " ".join(cells[index + 1].get_text(" ", strip=True).split())
                if label and label not in fields:
                    fields[label] = value or None
    return fields


def _parse_mayo_detail(
    document, details_url=None, planning_authority="Mayo County Council"
):
    soup = BeautifulSoup(document, "html.parser")
    if soup.select_one("#planningApplicationDetails") is None:
        return None
    details = _detail_fields(soup.select_one("#Details"))
    applicant = _detail_fields(soup.select_one("#Applicant"))
    development = _detail_fields(soup.select_one("#Development"))
    decision = _detail_fields(soup.select_one("#Decision"))
    application_number = details.get("File Number")
    if not application_number:
        return None
    return {
        "_source_layer": "eplanning",
        "ApplicationNumber": application_number,
        "ApplicationType": details.get("Application Type"),
        "ApplicationStatus": details.get("Planning Status"),
        "ReceivedDate": details.get("Received Date"),
        "DecisionDueDate": details.get("Decision Due Date"),
        "DecisionDate": decision.get("Decision Date") or details.get("Decision Date"),
        "Decision": decision.get("Decision Type") or details.get("Decision Type"),
        "WithdrawnDate": details.get("Withdrawn Date"),
        "FIRequestDate": details.get("Further Info Requested"),
        "FIRecDate": details.get("Further Info Received"),
        "GrantDate": decision.get("Grant Date"),
        "ExpiryDate": decision.get("Expiry Date"),
        "ApplicantName": applicant.get("Applicant name"),
        "ApplicantAddress": applicant.get("Applicant Address"),
        "DevelopmentAddress": development.get("Development Address") or "",
        "DevelopmentDescription": development.get("Development Description"),
        "PlanningAuthority": planning_authority,
        "LinkAppDetails": details_url,
    }


def _get_mayo_index_layer(url, where, number_field, batch_size=2000):
    session = requests.Session()
    numbers = []
    offset = 0
    while True:
        response = _mayo_request(
            session,
            "GET",
            url,
            params={
                "f": "json",
                "where": where,
                "outFields": number_field,
                "returnGeometry": "false",
                "orderByFields": number_field,
                "resultOffset": offset,
                "resultRecordCount": batch_size,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            raise RuntimeError(payload["error"])
        features = payload.get("features", [])
        numbers.extend(
            str(value).strip()
            for feature in features
            if (value := feature["attributes"].get(number_field)) and str(value).strip()
            if str(value).strip().isdigit()
        )
        offset += len(features)
        if not payload.get("exceededTransferLimit"):
            return numbers


def get_all_mayo_application_numbers():
    numbers_by_source = {}
    with ThreadPoolExecutor(max_workers=len(MAYO_INDEX_LAYERS)) as executor:
        futures = {
            executor.submit(_get_mayo_index_layer, url, where, field): source
            for source, url, where, field in MAYO_INDEX_LAYERS
        }
        for future in as_completed(futures):
            numbers_by_source[futures[future]] = future.result()
    unique = {}
    for source, _, _, _ in MAYO_INDEX_LAYERS:
        for number in numbers_by_source[source]:
            unique[number] = None
    return list(unique)


def get_all_mayo_applications(application_numbers=None):
    application_numbers = application_numbers or get_all_mayo_application_numbers()
    local = threading.local()

    def get_application(application_number):
        if not hasattr(local, "session"):
            local.session = requests.Session()
        details_url = MAYO_DETAIL_URL.format(application_number)
        response = _mayo_request(local.session, "GET", details_url)
        return _parse_mayo_detail(response.text, details_url)

    records = []
    bar = progressbar.ProgressBar(max_value=len(application_numbers), prefix="Mayo: ")
    with ThreadPoolExecutor(max_workers=MAYO_REQUEST_WORKERS) as executor:
        futures = [
            executor.submit(get_application, number) for number in application_numbers
        ]
        for completed, future in enumerate(as_completed(futures), 1):
            if record := future.result():
                records.append(record)
            bar.update(completed)
    bar.finish()
    return records


def download_mayo():
    objects = [MayoObject.parse(record) for record in get_all_mayo_applications()]
    write_to_db(mayo_db, MayoObject, objects)


class MayoObject(Model):
    objid = IntegerField()
    application_number = CharField(unique=True)
    address = TextField()
    searchable_address = TextField()
    planning_authority = CharField(null=True)
    postcode = CharField(null=True)
    applicant_name = CharField(null=True)
    applicant_address = TextField(null=True)
    application_type = CharField(null=True)
    application_status = CharField(null=True)
    description = TextField(null=True)
    decision = CharField(null=True)
    received_date = IntegerField(null=True)
    withdrawn_date = IntegerField(null=True)
    decision_date = IntegerField(null=True)
    decision_due_date = IntegerField(null=True)
    grant_date = IntegerField(null=True)
    expiry_date = IntegerField(null=True)
    appeal_reference = CharField(null=True)
    appeal_status = CharField(null=True)
    appeal_decision = CharField(null=True)
    appeal_decision_date = IntegerField(null=True)
    appeal_submitted_date = IntegerField(null=True)
    further_info_request_date = IntegerField(null=True)
    further_info_received_date = IntegerField(null=True)
    land_use_code = CharField(null=True)
    site_area = FloatField(null=True)
    residential_units = IntegerField(null=True)
    one_off_house = CharField(null=True)
    floor_area = FloatField(null=True)
    itm_easting = FloatField(null=True)
    itm_northing = FloatField(null=True)
    details_url = TextField(null=True)
    site_id = CharField(null=True)
    source_layer = CharField()

    class Meta:
        database = mayo_database

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.address = (self.address or "").strip()
        if not self.searchable_address:
            self.searchable_address = self.compute_searchable_address()

    def compute_searchable_address(self):
        return clean_address_for_comparison(self.address)

    def save(self, *args, **kwargs):
        self.searchable_address = self.compute_searchable_address()
        return super().save(*args, **kwargs)

    @staticmethod
    def parse(data):
        if isinstance(data, MayoObject):
            return data
        source = data.get("_source_layer", "national")
        if source == "eplanning":
            application_number = data.get("ApplicationNumber")
            digits = re.sub(r"\D", "", application_number or "")
            objid = (
                int(digits)
                if digits
                else zlib.crc32((application_number or "").encode("utf-8"))
            )
            return MayoObject(
                objid=objid,
                application_number=application_number,
                address=data.get("DevelopmentAddress") or "",
                planning_authority=data.get("PlanningAuthority"),
                applicant_name=data.get("ApplicantName"),
                applicant_address=data.get("ApplicantAddress"),
                application_type=data.get("ApplicationType"),
                application_status=data.get("ApplicationStatus"),
                description=data.get("DevelopmentDescription"),
                decision=data.get("Decision"),
                received_date=_mayo_date(data.get("ReceivedDate")),
                withdrawn_date=_mayo_date(data.get("WithdrawnDate")),
                decision_date=_mayo_date(data.get("DecisionDate")),
                decision_due_date=_mayo_date(data.get("DecisionDueDate")),
                grant_date=_mayo_date(data.get("GrantDate")),
                expiry_date=_mayo_date(data.get("ExpiryDate")),
                further_info_request_date=_mayo_date(data.get("FIRequestDate")),
                further_info_received_date=_mayo_date(data.get("FIRecDate")),
                details_url=data.get("LinkAppDetails"),
                source_layer=source,
            )
        if source == "pace":
            application_number = data.get("FileNumber")
            address_values = [data.get(f"DEV_ADD{number}") for number in range(1, 5)]
            return MayoObject(
                objid=data.get("FID"),
                application_number=application_number,
                address=", ".join(v.strip() for v in address_values if v and v.strip()),
                application_type=data.get("APP_TYPE"),
                application_status=data.get("APP_STATUS"),
                description=data.get("DESCRIPT"),
                decision=data.get("DECISION"),
                received_date=_mayo_date(data.get("RECEIVED")),
                decision_date=_mayo_date(data.get("DECDATE")),
                details_url=data.get("iPlan_Link"),
                source_layer=source,
            )
        if source == "historical":
            address_values = [
                data.get(f"dev_address_line{number}") for number in range(1, 4)
            ]
            applicant = " ".join(
                v.strip()
                for v in (data.get("forename"), data.get("surname"))
                if v and v.strip()
            )
            return MayoObject(
                objid=data.get("OBJECTID"),
                application_number=data.get("file_number"),
                address=", ".join(v.strip() for v in address_values if v and v.strip()),
                applicant_name=applicant or None,
                application_type=data.get("application_type"),
                description=data.get("development_descri"),
                decision=data.get("decision_code"),
                received_date=data.get("received_date"),
                withdrawn_date=data.get("withdrawn_date"),
                decision_date=data.get("decision_date"),
                grant_date=data.get("grant_date"),
                itm_easting=data.get("Easting"),
                itm_northing=data.get("Northing"),
                details_url=data.get("iPlan_Link"),
                source_layer=source,
            )
        applicant = " ".join(
            value.strip()
            for value in (data.get("ApplicantForename"), data.get("ApplicantSurname"))
            if value and value.strip()
        )
        return MayoObject(
            objid=data.get("OBJECTID"),
            application_number=data.get("ApplicationNumber"),
            address=data.get("DevelopmentAddress") or "",
            planning_authority=data.get("PlanningAuthority"),
            postcode=data.get("DevelopmentPostcode"),
            applicant_name=applicant or None,
            applicant_address=data.get("ApplicantAddress"),
            application_type=data.get("ApplicationType"),
            application_status=data.get("ApplicationStatus"),
            description=data.get("DevelopmentDescription"),
            decision=data.get("Decision"),
            received_date=data.get("ReceivedDate"),
            withdrawn_date=data.get("WithdrawnDate"),
            decision_date=data.get("DecisionDate"),
            decision_due_date=data.get("DecisionDueDate"),
            grant_date=data.get("GrantDate"),
            expiry_date=data.get("ExpiryDate"),
            appeal_reference=data.get("AppealRefNumber"),
            appeal_status=data.get("AppealStatus"),
            appeal_decision=data.get("AppealDecision"),
            appeal_decision_date=data.get("AppealDecisionDate"),
            appeal_submitted_date=data.get("AppealSubmittedDate"),
            further_info_request_date=data.get("FIRequestDate"),
            further_info_received_date=data.get("FIRecDate"),
            land_use_code=data.get("LandUseCode"),
            site_area=data.get("AreaofSite"),
            residential_units=data.get("NumResidentialUnits"),
            one_off_house=data.get("OneOffHouse"),
            floor_area=data.get("FloorArea"),
            itm_easting=data.get("ITMEasting"),
            itm_northing=data.get("ITMNorthing"),
            details_url=data.get("LinkAppDetails"),
            site_id=data.get("SiteId"),
            source_layer=source,
        )


def _mayo_date(value):
    if not value or not str(value).strip():
        return None
    if isinstance(value, int):
        return value
    parsed = datetime.strptime(value.strip(), "%d/%m/%Y").replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)


class MayoDB:
    def __init__(self):
        self.db = mayo_database
        self.db.connect(reuse_if_open=True)
        self.db.create_tables([MayoObject])

    def __len__(self):
        return MayoObject.select().count()

    def __iter__(self) -> Iterable[MayoObject]:
        return MayoObject.select().iterator()

    def recreate(self):
        self.db.drop_tables([MayoObject], safe=True)
        self.db.create_tables([MayoObject])

    def filter(
        self,
        address_substrs=None,
        exclude_address_substrs=None,
        address=None,
        partial=False,
    ) -> List[MayoObject]:
        query = MayoObject.select()
        if address:
            value = clean_address_for_comparison(address)
            query = query.where(
                MayoObject.searchable_address.contains(value)
                if partial
                else MayoObject.searchable_address == value
            )
        for value in address_substrs or []:
            query = query.where(
                MayoObject.searchable_address.contains(
                    clean_address_for_comparison(value)
                )
            )
        for value in exclude_address_substrs or []:
            query = query.where(
                ~MayoObject.searchable_address.contains(
                    clean_address_for_comparison(value)
                )
            )
        return list(query)


mayo_db = MayoDB()
