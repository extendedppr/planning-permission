from typing import Iterable, List

from peewee import CharField, FloatField, IntegerField, Model, SqliteDatabase, TextField

from planning_permission.settings import WICKLOW_DB_LOCATION
from planning_permission.utils import (
    clean_address_for_comparison,
    arcgis_download,
    write_to_db,
)


wicklow_database = SqliteDatabase(WICKLOW_DB_LOCATION)

WICKLOW_URL = "https://services.arcgis.com/hQOfkHGHCu8mgDpG/arcgis/rest/services/External_Planning_Apps/FeatureServer/0/query"


def download_wicklow():
    objects = [
        WicklowObject.parse(record)
        for record in arcgis_download(WICKLOW_URL, skip_sort=True, prefix="Wicklow: ")
    ]
    write_to_db(wicklow_db, WicklowObject, objects)


class WicklowObject(Model):
    objid = IntegerField(unique=True)
    application_number = CharField(index=True)
    address = TextField()
    searchable_address = TextField()

    applicant_name = CharField(null=True)
    application_type = CharField(null=True)
    application_status = CharField(null=True)
    status = CharField(null=True)
    description = TextField(null=True)
    decision = CharField(null=True)
    decision_code = CharField(null=True)
    received_date = IntegerField(null=True)
    decision_date = IntegerField(null=True)
    withdrawn_date = IntegerField(null=True)
    appeal_notification_date = IntegerField(null=True)
    eplanning_link = TextField(null=True)
    related_file_number = CharField(null=True)
    latitude = FloatField(null=True)
    longitude = FloatField(null=True)

    class Meta:
        database = wicklow_database

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
        if isinstance(data, WicklowObject):
            return data
        address = ", ".join(
            value.strip()
            for value in (
                data.get("dev_address_line1"),
                data.get("dev_address_line2"),
                data.get("dev_address_line3"),
            )
            if value and value.strip()
        )
        applicant = " ".join(
            value.strip()
            for value in (data.get("forename"), data.get("surname"))
            if value and value.strip()
        )
        return WicklowObject(
            objid=data.get("OBJECTID"),
            application_number=data.get("file_number"),
            address=address,
            applicant_name=applicant,
            application_type=data.get("ApplicationType"),
            application_status=data.get("status_desc"),
            status=data.get("STATUS"),
            description=data.get("development_descri"),
            decision=data.get("decision"),
            decision_code=data.get("decision_code"),
            received_date=data.get("received_date"),
            decision_date=data.get("decision_date"),
            withdrawn_date=data.get("withdrawn_date"),
            appeal_notification_date=data.get("abp_notification_date"),
            eplanning_link=data.get("Link2ePlan"),
            related_file_number=data.get("fk_paapplicfile_nu"),
            # The published field names are reversed in this service.
            latitude=data.get("Long"),
            longitude=data.get("Lat"),
        )


class WicklowDB:
    def __init__(self):
        self.db = wicklow_database
        self.db.connect(reuse_if_open=True)
        self.db.create_tables([WicklowObject])

    def __len__(self):
        return WicklowObject.select().count()

    def __iter__(self) -> Iterable[WicklowObject]:
        return WicklowObject.select().iterator()

    def recreate(self):
        self.db.drop_tables([WicklowObject], safe=True)
        self.db.create_tables([WicklowObject])

    def filter(
        self,
        address_substrs=None,
        exclude_address_substrs=None,
        address=None,
        partial=False,
    ) -> List[WicklowObject]:
        query = WicklowObject.select()
        if address:
            address = clean_address_for_comparison(address)
            query = query.where(
                WicklowObject.searchable_address.contains(address)
                if partial
                else WicklowObject.searchable_address == address
            )
        for value in address_substrs or []:
            query = query.where(
                WicklowObject.searchable_address.contains(
                    clean_address_for_comparison(value)
                )
            )
        for value in exclude_address_substrs or []:
            query = query.where(
                ~WicklowObject.searchable_address.contains(
                    clean_address_for_comparison(value)
                )
            )
        return list(query)


wicklow_db = WicklowDB()
