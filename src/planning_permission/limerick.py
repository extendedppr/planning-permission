import math
import time
from typing import Iterable, List
from urllib.parse import unquote_plus

import progressbar
import requests
from peewee import CharField, IntegerField, Model, SqliteDatabase, TextField, chunked

from planning_permission.settings import LIMERICK_DB_LOCATION, SLEEP_BETWEEN_REQUESTS
from planning_permission.utils import arcgis_download, clean_address_for_comparison


limerick_database = SqliteDatabase(LIMERICK_DB_LOCATION)
LIMERICK_BATCH_SIZE = 250
LIMERICK_REGISTER_URL = (
    "https://services.arcgis.com/NzlPQPKn5QF9v2US/arcgis/rest/services/"
    "IrishPlanningApplications/FeatureServer/0/query"
)
LIMERICK_REGISTER_WHERE = "PlanningAuthority = 'Limerick County Council'"


def limerick_request_data(start, length, draw):
    LIMERICK_COLUMNS = (
        "geom",
        "file_number",
        "siteid",
        "year",
        "decision",
        "type",
        "status",
        "description",
        "applicant_full_name",
        "development_address",
        "cso_category",
        "cso_category_description",
        "area",
        "unit_of_measure",
        "unit_description",
        "unit_number",
    )
    data = {
        "draw": draw,
        "order[0][column]": 0,
        "order[0][dir]": "asc",
        "start": start,
        "length": length,
        "search[value]": "",
        "search[regex]": "false",
        "tableName": "planning_application_points",
        "workspaceName": "lcccgis",
        "datastoreID": 36800,
        "sqlScript": "WHMHZmwyXHWos8QbkCh58wn+Xk3ro+Dz8ajb67YMYxHdoQI0xUF8KgFw8r6biRDwRvFe9TyglDfqbvoggSKba/Hrbz/4k8C54Im7JP8o+q8=",
        "ShowFeaturesInBrowseAllFeatures": "",
    }
    for index, column in enumerate(LIMERICK_COLUMNS):
        prefix = f"columns[{index}]"
        data[f"{prefix}[data]"] = column
        data[f"{prefix}[name]"] = ""
        data[f"{prefix}[searchable]"] = "true"
        data[f"{prefix}[orderable]"] = "false" if index == 0 else "true"
        data[f"{prefix}[search][value]"] = ""
        data[f"{prefix}[search][regex]"] = "false"
    return data


def get_all_limerick_applications(session=None, batch_size=LIMERICK_BATCH_SIZE):
    session = session or requests.Session()
    session.headers.update(
        {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": "https://azimuth.azimap.com/embed/30076",
            "X-Requested-With": "XMLHttpRequest",
        }
    )
    session.get(
        "https://azimuth.azimap.com/embed/30076", timeout=120
    ).raise_for_status()

    records_by_number = {}
    start = 0
    draw = 1
    bar = None
    while True:
        response = session.post(
            (
                "https://azimuth.azimap.com/"
                "WebService/AllFeaturesDataTable.asmx/GetFeatures"
            ),
            data=limerick_request_data(start, batch_size, draw),
            timeout=120,
        )
        if not response.ok:
            raise requests.HTTPError(
                f"Azimap request failed at start={start}, length={batch_size}: "
                f"{response.status_code} {response.text[:500]}",
                response=response,
            )
        payload = response.json()
        page = payload.get("data", [])
        total = payload.get("recordsFiltered", payload.get("recordsTotal", 0))
        if bar is None:
            bar = progressbar.ProgressBar(max_value=total, prefix="Limerick: ")
            bar.start()
        if not page:
            break

        for record in page:
            records_by_number[record["file_number"]] = record
        start += len(page)
        bar.update(min(start, total))
        if start >= total:
            break
        draw += 1
        time.sleep(max(SLEEP_BETWEEN_REQUESTS, 3))

    if bar is not None:
        bar.finish()

    return list(records_by_number.values())


def download_limerick():
    records = get_all_limerick_applications()
    register = arcgis_download(
        LIMERICK_REGISTER_URL,
        skip_sort=True,
        where=LIMERICK_REGISTER_WHERE,
        prefix="Limerick dates: ",
    )
    details_by_number = {
        str(record.get("ApplicationNumber")).strip().casefold(): record
        for record in register
        if record.get("ApplicationNumber") not in (None, "")
    }
    objects = []
    for record in records:
        number = record.get("file_number")
        details = (
            details_by_number.get(str(number).strip().casefold()) if number else None
        )
        objects.append(LimerickObject.parse(record, details))

    batch_size = 500
    total_batches = math.ceil(len(objects) / batch_size)
    print(f"About to insert {len(objects)} objects into the database")

    limerick_db.recreate()
    with limerick_db.db.atomic():
        for batch in progressbar.progressbar(
            chunked(objects, batch_size),
            max_value=total_batches,
            prefix="Limerick: ",
        ):
            LimerickObject.bulk_create(batch, batch_size=batch_size)


class LimerickObject(Model):
    application_number = CharField(unique=True)
    address = TextField()
    searchable_address = TextField()

    site_id = CharField(null=True)
    year = IntegerField(null=True)
    decision = CharField(null=True)
    application_type = CharField(null=True)
    application_status = CharField(null=True)
    received_date = IntegerField(null=True)
    decision_date = IntegerField(null=True)
    description = TextField(null=True)
    applicant_name = CharField(null=True)
    development_address = TextField(null=True)
    cso_category = CharField(null=True)
    cso_category_description = TextField(null=True)
    area = CharField(null=True)
    unit_of_measure = CharField(null=True)
    unit_description = TextField(null=True)
    unit_number = CharField(null=True)

    class Meta:
        database = limerick_database

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.address = (self.address or "").strip().replace(" ,", ",")
        while "  " in self.address:
            self.address = self.address.replace("  ", " ")
        if not self.searchable_address:
            self.searchable_address = self.compute_searchable_address()

    def compute_searchable_address(self):
        return clean_address_for_comparison(self.address)

    def save(self, *args, **kwargs):
        self.searchable_address = self.compute_searchable_address()
        return super().save(*args, **kwargs)

    def __repr__(self):
        return f"{self.application_number}: {self.address}"

    @staticmethod
    def parse(data, details=None):
        if isinstance(data, LimerickObject):
            return data
        details = details or {}

        field_map = {
            "file_number": "application_number",
            "siteid": "site_id",
            "type": "application_type",
            "status": "application_status",
            "applicant_full_name": "applicant_name",
        }
        parsed = {}
        for key, value in data.items():
            key = field_map.get(key, key)
            if key not in LimerickObject._meta.fields or key == "geom":
                continue
            if isinstance(value, str):
                value = unquote_plus(value).strip() or None
            parsed[key] = value

        parsed.setdefault("address", parsed.get("development_address") or "")
        parsed["received_date"] = details.get("ReceivedDate")
        parsed["decision_date"] = details.get("DecisionDate")
        return LimerickObject(**parsed)


class LimerickDB:
    def __init__(self):
        self.db = limerick_database
        self.db.connect(reuse_if_open=True)
        self.db.create_tables([LimerickObject])

    def __len__(self):
        return LimerickObject.select().count()

    def __iter__(self) -> Iterable[LimerickObject]:
        return LimerickObject.select().iterator()

    def recreate(self):
        self.db.drop_tables([LimerickObject], safe=True)
        self.db.create_tables([LimerickObject])

    def filter(
        self,
        address_substrs=None,
        exclude_address_substrs=None,
        address=None,
        county=None,
        eircode=None,
        eircode_routing_key=None,
        partial: bool = False,
    ) -> List[LimerickObject]:
        filters = {}

        query = LimerickObject.select()

        for field, value in filters.items():
            if value is not None:
                field_name = getattr(LimerickObject, field)
                if partial:
                    query = query.where(field_name.ilike(f"%{value}%"))
                else:
                    query = query.where(field_name.ilike(value))

        if address:
            address = address.replace(" ", "").replace(",", "").lower()
            if partial:
                query = query.where(LimerickObject.searchable_address.contains(address))
            else:
                query = query.where(LimerickObject.searchable_address == address)

        if address_substrs:
            for address_substr in address_substrs:
                query = query.where(
                    LimerickObject.searchable_address.contains(
                        clean_address_for_comparison(address_substr)
                    )
                )

        if exclude_address_substrs:
            for exclude_address_substr in exclude_address_substrs:
                query = query.where(
                    ~(
                        LimerickObject.searchable_address.contains(
                            clean_address_for_comparison(exclude_address_substr)
                        )
                    )
                )

        return [obj for obj in query]


limerick_db = LimerickDB()
