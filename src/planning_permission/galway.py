import re
from typing import Iterable, List

import progressbar
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from peewee import (
    Model,
    TextField,
    IntegerField,
    CharField,
    FloatField,
    SqliteDatabase,
    IntegrityError,
)

from planning_permission.settings import GALWAY_DB_LOCATION
from planning_permission.utils import (
    clean_address_for_comparison,
    itm_to_lat_lng,
    write_to_db,
)

GALWAY_URL = (
    "https://services1.arcgis.com/mJI7JYqAOKXPG7Hh/arcgis/rest/services/"
    "GCC_PlanningRegisterPts_16/FeatureServer/2/query"
)
GALWAY_1995_2015_URL = (
    "https://services1.arcgis.com/mJI7JYqAOKXPG7Hh/arcgis/rest/services/"
    "GCC_PlanningRegisterPts_95_15/FeatureServer/0/query"
)
GALWAY_HISTORICAL_URL = (
    "https://services1.arcgis.com/mJI7JYqAOKXPG7Hh/arcgis/rest/services/"
    "GCC_PlanningRegisterHistorical/FeatureServer/0/query"
)
GALWAY_LAYERS = (
    (GALWAY_HISTORICAL_URL, "Planning_Ref", "Galway historical: "),
    (GALWAY_1995_2015_URL, "ApplicationNumber", "Galway 1995–2015: "),
    (GALWAY_URL, "ApplicationNumber", "Galway 2016+: "),
)
GALWAY_WHERE = "1=1"
GALWAY_PAGE_SIZE = 1000
GALWAY_REQUEST_TIMEOUT = 60
GALWAY_RETRY_STATUSES = (429, 500, 502, 503, 504)
GALWAY_REQUEST_ATTEMPTS = 5


def _galway_session():
    session = requests.Session()
    retries = Retry(
        total=GALWAY_REQUEST_ATTEMPTS,
        backoff_factor=1,
        status_forcelist=GALWAY_RETRY_STATUSES,
        allowed_methods=("GET",),
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


def _get_galway_layer(url, session, batch_size, prefix):
    count_response = session.get(
        url,
        params={"f": "json", "where": GALWAY_WHERE, "returnCountOnly": "true"},
        timeout=GALWAY_REQUEST_TIMEOUT,
    )
    count_response.raise_for_status()
    count_payload = count_response.json()
    if count_payload.get("error"):
        raise RuntimeError(count_payload["error"])
    total = count_payload["count"]

    records = []
    offset = 0
    bar = progressbar.ProgressBar(max_value=total, prefix=prefix)
    bar.start()
    while offset < total:
        response = session.get(
            url,
            params={
                "f": "json",
                "where": GALWAY_WHERE,
                "returnGeometry": "false",
                "outFields": "*",
                "orderByFields": "OBJECTID ASC",
                "resultOffset": offset,
                "resultRecordCount": batch_size,
            },
            timeout=GALWAY_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            raise RuntimeError(payload["error"])
        page = [feature["attributes"] for feature in payload.get("features", [])]
        if not page:
            break
        records.extend(page)
        offset += len(page)
        bar.update(min(offset, total))
        if payload.get("exceededTransferLimit") is False:
            break
    bar.finish()
    return records


def _normalise_galway_reference(value):
    return re.sub(r"[^a-z0-9]", "", str(value).strip().casefold())


def get_all_galway_applications(
    session=None, batch_size=GALWAY_PAGE_SIZE, layers=GALWAY_LAYERS
):
    session = session or _galway_session()
    records_by_reference = {}
    records_without_reference = []
    # Layers are ordered oldest to newest so a richer/current record replaces
    # a sparse historical index record when references overlap.
    for url, reference_field, prefix in layers:
        records = _get_galway_layer(url, session, batch_size, prefix)
        for record in records:
            reference = record.get(reference_field)
            if reference in (None, ""):
                records_without_reference.append(record)
                continue
            records_by_reference[_normalise_galway_reference(reference)] = record
    return list(records_by_reference.values()) + records_without_reference


def parse_galway_application(data):
    lat, lng = itm_to_lat_lng(data.get("ITMEasting"), data.get("ITMNorthing"))
    return GalwayObject.parse(
        {
            "address": data.get("Location") or "",
            "objid": data.get("OBJECTID"),
            "application_number": data.get("ApplicationNumber")
            or data.get("Planning_Ref"),
            "applicant_name": data.get("ApplicantName"),
            "received_date": data.get("ReceivedDate"),
            "application_type": data.get("ApplicationType"),
            "application_status": data.get("ApplicationStatus"),
            "description": data.get("Description"),
            "decision": data.get("Decision"),
            "decision_date": data.get("DecisionDate"),
            "decision_due_date": data.get("DecisionDueDate"),
            "withdrawn_date": data.get("WithdrawnDate"),
            "grant_date": data.get("GrantDate"),
            "expiry_date": data.get("ExpiryDate"),
            "appeal_notification_date": data.get("AppealNotificationDate"),
            "appeal_ref_num": data.get("AppealRefNum"),
            "appeal_decision": data.get("AppealDecision"),
            "appeal_decision_date": data.get("AppealDecisionDate"),
            "lat": lat,
            "lng": lng,
            "more_info": data.get("MoreInfo"),
            "global_id": data.get("GlobalID"),
        }
    )


def download_galway():
    records = get_all_galway_applications()
    objects = [parse_galway_application(record) for record in records]
    write_to_db(galway_db, GalwayObject, objects)


class GalwayObject(Model):
    objid = IntegerField(null=True)
    address = CharField()
    searchable_address = CharField()

    application_number = CharField(null=True)
    applicant_name = CharField(null=True)
    application_type = CharField(null=True)
    application_status = CharField(null=True)
    description = TextField(null=True)
    decision = CharField(null=True)

    received_date = CharField(null=True)
    withdrawn_date = CharField(null=True)
    grant_date = CharField(null=True)
    expiry_date = CharField(null=True)
    decision_date = CharField(null=True)
    decision_due_date = CharField(null=True)

    appeal_notification_date = CharField(null=True)
    appeal_ref_num = CharField(null=True)
    appeal_decision = CharField(null=True)
    appeal_decision_date = CharField(null=True)

    lat = FloatField(null=True)
    lng = FloatField(null=True)
    more_info = CharField(null=True)
    global_id = CharField(null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.address = self.address.strip().replace(" ,", ",")
        while "  " in self.address:
            self.address = self.address.replace("  ", " ")

        if not self.searchable_address:
            self.searchable_address = self.compute_searchable_address()

    class Meta:
        database = SqliteDatabase(GALWAY_DB_LOCATION)

    def save(self, *args, **kwargs):
        self.searchable_address = self.compute_searchable_address()
        try:
            return super(GalwayObject, self).save(*args, **kwargs)
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
        if isinstance(data, GalwayObject):
            return data
        if isinstance(data, dict):
            data.pop(None, None)
        return GalwayObject(**data)


class GalwayDB:
    def __init__(self) -> None:
        self.create_connection()

    def __len__(self) -> int:
        return GalwayObject.select().count()

    def __iter__(self) -> Iterable[GalwayObject]:
        return GalwayObject.select().iterator()

    def drop_data(self) -> None:
        GalwayObject.delete().execute()

    def recreate(self) -> None:
        self.db.drop_tables([GalwayObject], safe=True)
        self.db.create_tables([GalwayObject])

    def create_connection(self) -> None:
        self.db = SqliteDatabase(GALWAY_DB_LOCATION)
        self.db.connect()
        self.db.create_tables([GalwayObject])

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
    ) -> List[GalwayObject]:
        filters = {}

        query = GalwayObject.select()

        for field, value in filters.items():
            if value is not None:
                field_name = getattr(GalwayObject, field)
                if partial:
                    query = query.where(field_name.ilike(f"%{value}%"))
                else:
                    query = query.where(field_name.ilike(value))

        if address:
            address = address.replace(" ", "").replace(",", "").lower()
            if partial:
                query = query.where(GalwayObject.searchable_address.contains(address))
            else:
                query = query.where(GalwayObject.searchable_address == address)

        if address_substrs:
            for address_substr in address_substrs:
                query = query.where(
                    GalwayObject.searchable_address.contains(
                        clean_address_for_comparison(address_substr)
                    )
                )

        if exclude_address_substrs:
            for exclude_address_substr in exclude_address_substrs:
                query = query.where(
                    ~(
                        GalwayObject.searchable_address.contains(
                            clean_address_for_comparison(exclude_address_substr)
                        )
                    )
                )

        return [obj for obj in query]


galway_db = GalwayDB()
