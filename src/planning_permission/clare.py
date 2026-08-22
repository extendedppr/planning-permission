from typing import Iterable, List

from peewee import CharField, IntegerField, Model, SqliteDatabase, TextField

from planning_permission.settings import CLARE_DB_LOCATION
from planning_permission.utils import (
    arcgis_download,
    clean_address_for_comparison,
    write_to_db,
)


CLARE_SITES_URL = (
    "https://services8.arcgis.com/OnLILyV2xWhWjtPS/arcgis/rest/services/"
    "Planning_Applications_WFL1/FeatureServer/1/query"
)
CLARE_REGISTER_URL = (
    "https://services.arcgis.com/NzlPQPKn5QF9v2US/arcgis/rest/services/"
    "IrishPlanningApplications/FeatureServer/0/query"
)
CLARE_WHERE = "PlanningAuthority = 'Clare County Council'"
clare_database = SqliteDatabase(CLARE_DB_LOCATION)


def download_clare():
    # This view advertises OBJECTID_1 but rejects it in orderByFields.
    sites = arcgis_download(CLARE_SITES_URL, skip_sort=True, prefix="Clare sites: ")
    register = arcgis_download(
        CLARE_REGISTER_URL,
        skip_sort=True,
        where=CLARE_WHERE,
        prefix="Clare details: ",
    )
    details_by_number = {
        str(record.get("ApplicationNumber")).strip().casefold(): record
        for record in register
        if record.get("ApplicationNumber") not in (None, "")
    }
    objects = []
    for site in sites:
        number = site.get("FileNumber")
        details = (
            details_by_number.get(str(number).strip().casefold()) if number else None
        )
        objects.append(ClareObject.parse(site, details))
    write_to_db(clare_db, ClareObject, objects)


class ClareObject(Model):
    objid = IntegerField(unique=True)
    source_object_id = IntegerField(null=True)
    application_number = CharField(unique=True)
    address = TextField(default="")
    searchable_address = TextField(default="")
    planning_authority = CharField(null=True)
    application_type = CharField(null=True)
    application_status = CharField(null=True)
    description = TextField(null=True)
    decision = CharField(null=True)
    received_date = IntegerField(null=True)
    decision_date = IntegerField(null=True)
    site_id = CharField(null=True)
    details_url = TextField(null=True)

    class Meta:
        database = clare_database

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.address = (self.address or "").strip()
        if not self.searchable_address:
            self.searchable_address = clean_address_for_comparison(self.address)

    def save(self, *args, **kwargs):
        self.searchable_address = clean_address_for_comparison(self.address)
        return super().save(*args, **kwargs)

    @staticmethod
    def parse(data, details=None):
        if isinstance(data, ClareObject):
            return data
        details = details or {}
        return ClareObject(
            objid=data.get("OBJECTID_1") or data.get("OBJECTID"),
            source_object_id=data.get("OBJECTID"),
            application_number=data.get("FileNumber")
            or details.get("ApplicationNumber")
            or data.get("ApplicationNumber"),
            address=details.get("DevelopmentAddress") or "",
            planning_authority=details.get("PlanningAuthority"),
            application_type=data.get("ApplicationType")
            or details.get("ApplicationType"),
            application_status=details.get("ApplicationStatus"),
            description=details.get("DevelopmentDescription"),
            decision=details.get("Decision"),
            received_date=details.get("ReceivedDate"),
            decision_date=details.get("DecisionDate"),
            site_id=data.get("SiteID") or details.get("SiteId"),
            details_url=details.get("LinkAppDetails"),
        )


class ClareDB:
    def __init__(self):
        self.db = clare_database
        self.db.connect(reuse_if_open=True)
        self.db.create_tables([ClareObject])

    def __len__(self):
        return ClareObject.select().count()

    def __iter__(self) -> Iterable[ClareObject]:
        return ClareObject.select().iterator()

    def recreate(self):
        self.db.drop_tables([ClareObject], safe=True)
        self.db.create_tables([ClareObject])

    def filter(
        self,
        address_substrs=None,
        exclude_address_substrs=None,
        address=None,
        partial=False,
    ) -> List[ClareObject]:
        query = ClareObject.select()
        if address or address_substrs:
            return []
        return list(query)


clare_db = ClareDB()
