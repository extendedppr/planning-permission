import math
import time
from typing import Iterable, List

import progressbar
import requests
from peewee import (
    CharField,
    FloatField,
    IntegerField,
    Model,
    SqliteDatabase,
    TextField,
    chunked,
)

from planning_permission.settings import LOUTH_DB_LOCATION, SLEEP_BETWEEN_REQUESTS
from planning_permission.utils import clean_address_for_comparison


louth_database = SqliteDatabase(LOUTH_DB_LOCATION)

LOUTH_URL = (
    "https://services-eu1.arcgis.com/021lZtUUnzKYjk3l/arcgis/rest/services/"
    "Testing_PACE/FeatureServer/0/query"
)


def get_all_louth_applications(session=None, batch_size=2000):
    session = session or requests.Session()
    count_response = session.get(
        LOUTH_URL,
        params={"f": "json", "where": "1=1", "returnCountOnly": "true"},
        timeout=120,
    )
    count_response.raise_for_status()
    total = count_response.json()["count"]
    bar = progressbar.ProgressBar(max_value=total, prefix="Louth: ")
    bar.start()
    records, offset = [], 0
    while offset < total:
        response = session.get(
            LOUTH_URL,
            params={
                "f": "json",
                "where": "1=1",
                "outFields": "*",
                "returnGeometry": "false",
                "resultOffset": offset,
                "resultRecordCount": batch_size,
                "orderByFields": "FID ASC",
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
        records.extend(page)
        offset += len(page)
        bar.update(min(offset, total))
        if payload.get("exceededTransferLimit") is False:
            break
        time.sleep(SLEEP_BETWEEN_REQUESTS)
    bar.finish()
    return records


def download_louth():
    objects = [LouthObject.parse(record) for record in get_all_louth_applications()]
    louth_db.recreate()
    batch_size = 500
    total_batches = math.ceil(len(objects) / batch_size)
    print(f"About to insert {len(objects)} objects into the database")
    with louth_db.db.atomic():
        for batch in progressbar.progressbar(
            chunked(objects, batch_size),
            max_value=total_batches,
            prefix="Louth: ",
        ):
            LouthObject.bulk_create(batch, batch_size=batch_size)


class LouthObject(Model):
    objid = IntegerField(unique=True)
    application_number = CharField(unique=True)
    address = TextField()
    searchable_address = TextField()
    applicant_name = CharField(null=True)
    received_date = CharField(null=True)
    decision_date = CharField(null=True)
    manager_order_decision_date = CharField(null=True)
    description = TextField(null=True)
    decision = CharField(null=True)
    application_status = CharField(null=True)
    numeric_file_number = IntegerField(null=True)
    year = CharField(null=True)
    development_name = CharField(null=True)
    global_id = CharField(null=True)
    created_date = IntegerField(null=True)
    edited_date = IntegerField(null=True)
    shape_area = FloatField(null=True)
    shape_length = FloatField(null=True)

    class Meta:
        database = louth_database

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.address = (self.address or "").strip()
        while "  " in self.address:
            self.address = self.address.replace("  ", " ")
        if not self.searchable_address:
            self.searchable_address = self.compute_searchable_address()

    def compute_searchable_address(self):
        return clean_address_for_comparison(self.address)

    def save(self, *args, **kwargs):
        self.searchable_address = self.compute_searchable_address()
        return super().save(*args, **kwargs)

    @staticmethod
    def parse(data):
        if isinstance(data, LouthObject):
            return data
        return LouthObject(
            objid=data.get("FID"),
            application_number=data.get("FileRef"),
            address=data.get("AllDevAdd") or data.get("Loc") or "",
            applicant_name=data.get("AppName"),
            received_date=data.get("RedDate"),
            decision_date=data.get("Dec_date"),
            manager_order_decision_date=data.get("MO_Dec_Dat"),
            description=data.get("DevDesc"),
            decision=data.get("Decision"),
            application_status=data.get("AppStatus"),
            numeric_file_number=data.get("FileNo"),
            year=data.get("Year"),
            development_name=data.get("DevName"),
            global_id=data.get("GlobalID"),
            created_date=data.get("CreationDate_2"),
            edited_date=data.get("EditDate_2"),
            shape_area=data.get("Shape__Area"),
            shape_length=data.get("Shape__Length"),
        )


class LouthDB:
    def __init__(self):
        self.db = louth_database
        self.db.connect(reuse_if_open=True)
        self.db.create_tables([LouthObject])

    def __len__(self):
        return LouthObject.select().count()

    def __iter__(self) -> Iterable[LouthObject]:
        return LouthObject.select().iterator()

    def recreate(self):
        self.db.drop_tables([LouthObject], safe=True)
        self.db.create_tables([LouthObject])

    def filter(
        self,
        address_substrs=None,
        exclude_address_substrs=None,
        address=None,
        partial=False,
    ) -> List[LouthObject]:
        query = LouthObject.select()
        if address:
            value = clean_address_for_comparison(address)
            query = query.where(
                LouthObject.searchable_address.contains(value)
                if partial
                else LouthObject.searchable_address == value
            )
        for value in address_substrs or []:
            query = query.where(
                LouthObject.searchable_address.contains(
                    clean_address_for_comparison(value)
                )
            )
        for value in exclude_address_substrs or []:
            query = query.where(
                ~LouthObject.searchable_address.contains(
                    clean_address_for_comparison(value)
                )
            )
        return list(query)


louth_db = LouthDB()
