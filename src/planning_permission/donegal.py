import math
import time
from typing import Iterable, List

import progressbar
import requests
from peewee import CharField, IntegerField, Model, SqliteDatabase, TextField, chunked

from planning_permission.settings import DONEGAL_DB_LOCATION, SLEEP_BETWEEN_REQUESTS
from planning_permission.utils import clean_address_for_comparison


donegal_database = SqliteDatabase(DONEGAL_DB_LOCATION)


DONEGAL_LAYERS = (
    (
        "since_2010",
        "https://services2.arcgis.com/WRtfelnPg3R7bCEW/arcgis/rest/services/"
        "2010_2019_apps/FeatureServer/0/query",
    ),
    (
        "2005_2009",
        "https://services2.arcgis.com/WRtfelnPg3R7bCEW/arcgis/rest/services/"
        "PlanningPointsSplit/FeatureServer/1/query",
    ),
    (
        "2000_2004",
        "https://services2.arcgis.com/WRtfelnPg3R7bCEW/arcgis/rest/services/"
        "PlanningPointsSplit/FeatureServer/2/query",
    ),
    (
        "pre_2000",
        "https://services2.arcgis.com/WRtfelnPg3R7bCEW/arcgis/rest/services/"
        "PlanningPointsSplit/FeatureServer/3/query",
    ),
)


def get_all_donegal_applications(session=None, layers=DONEGAL_LAYERS, batch_size=2000):
    session = session or requests.Session()
    counts = []
    for _, url in layers:
        response = session.get(
            url,
            params={"f": "json", "where": "1=1", "returnCountOnly": "true"},
            timeout=120,
        )
        response.raise_for_status()
        counts.append(response.json()["count"])

    total = sum(counts)
    bar = progressbar.ProgressBar(max_value=total, prefix="Donegal: ")
    bar.start()
    records = []

    for (source_layer, url), layer_count in zip(layers, counts):
        offset = 0
        while offset < layer_count:
            response = session.get(
                url,
                params={
                    "f": "json",
                    "where": "1=1",
                    "outFields": "*",
                    "returnGeometry": "false",
                    "resultOffset": offset,
                    "resultRecordCount": batch_size,
                    "orderByFields": "OBJECTID ASC",
                },
                timeout=120,
            )
            response.raise_for_status()
            payload = response.json()
            if "error" in payload:
                raise RuntimeError(payload["error"])
            page = [feature["attributes"] for feature in payload.get("features", [])]
            if not page:
                break
            for record in page:
                record["_source_layer"] = source_layer
            records.extend(page)
            offset += len(page)
            bar.update(min(len(records), total))
            if payload.get("exceededTransferLimit") is False:
                break
            time.sleep(SLEEP_BETWEEN_REQUESTS)

    bar.finish()
    return records


def download_donegal():
    records = get_all_donegal_applications()
    objects = [DonegalObject.parse(record) for record in records]

    donegal_db.recreate()
    batch_size = 500
    total_batches = math.ceil(len(objects) / batch_size)
    print(f"About to insert {len(objects)} objects into the database")
    with donegal_db.db.atomic():
        for batch in progressbar.progressbar(
            chunked(objects, batch_size),
            max_value=total_batches,
            prefix="Donegal: ",
        ):
            DonegalObject.bulk_create(batch, batch_size=batch_size)


class DonegalObject(Model):
    application_number = CharField(index=True)
    address = TextField()
    searchable_address = TextField()

    source_layer = CharField()
    source_object_id = IntegerField()
    applicant_name = CharField(null=True)
    received_date = CharField(null=True)
    decision_date = CharField(null=True)
    description = TextField(null=True)
    decision_description = TextField(null=True)
    application_status = CharField(null=True)
    decision = CharField(null=True)
    eplanning_link = TextField(null=True)
    document_link = TextField(null=True)

    class Meta:
        database = donegal_database
        indexes = ((("source_layer", "source_object_id"), True),)

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
        if isinstance(data, DonegalObject):
            return data
        return DonegalObject(
            application_number=data.get("FILE_NUMBER") or data.get("FILE_NUMBE"),
            address=data.get("location_key") or data.get("location_k") or "",
            source_layer=data["_source_layer"],
            source_object_id=data["OBJECTID"],
            applicant_name=data.get("ApplicName"),
            received_date=data.get("received_date") or data.get("received_d"),
            decision_date=data.get("decision_date") or data.get("decision_d"),
            description=data.get("development_descri") or data.get("developmen"),
            decision_description=(
                data.get("decision_description") or data.get("decision00")
            ),
            application_status=(
                data.get("ApplicationStatus") or data.get("Applicatio")
            ),
            decision=data.get("DEC_CODE") or data.get("decision_c"),
            eplanning_link=data.get("ePlanLink"),
            document_link=data.get("linkpcdoc"),
        )


class DonegalDB:
    def __init__(self):
        self.db = donegal_database
        self.db.connect(reuse_if_open=True)
        self.db.create_tables([DonegalObject])

    def __len__(self):
        return DonegalObject.select().count()

    def __iter__(self) -> Iterable[DonegalObject]:
        return DonegalObject.select().iterator()

    def recreate(self):
        self.db.drop_tables([DonegalObject], safe=True)
        self.db.create_tables([DonegalObject])

    def filter(
        self,
        address_substrs=None,
        exclude_address_substrs=None,
        address=None,
        partial=False,
    ) -> List[DonegalObject]:
        query = DonegalObject.select()
        if address:
            address = clean_address_for_comparison(address)
            if partial:
                query = query.where(DonegalObject.searchable_address.contains(address))
            else:
                query = query.where(DonegalObject.searchable_address == address)
        for value in address_substrs or []:
            query = query.where(
                DonegalObject.searchable_address.contains(
                    clean_address_for_comparison(value)
                )
            )
        for value in exclude_address_substrs or []:
            query = query.where(
                ~DonegalObject.searchable_address.contains(
                    clean_address_for_comparison(value)
                )
            )
        return list(query)


donegal_db = DonegalDB()
