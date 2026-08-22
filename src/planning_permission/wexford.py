from typing import Iterable, List

from peewee import CharField, IntegerField, Model, SqliteDatabase, TextField

from planning_permission.settings import WEXFORD_DB_LOCATION
from planning_permission.utils import (
    clean_address_for_comparison,
    arcgis_download,
    write_to_db,
)


wexford_database = SqliteDatabase(WEXFORD_DB_LOCATION)
WEXFORD_URL = "https://services-eu1.arcgis.com/SEIHigRppeVyVssQ/arcgis/rest/services/Planning_Apps_Public_Search/FeatureServer/0/query"
WEXFORD_DETAILS_URL = (
    "https://services-eu1.arcgis.com/SEIHigRppeVyVssQ/arcgis/rest/services/"
    "Wexford_Planning_Apps_Point_and_Polygons_View/FeatureServer/0/query"
)
WEXFORD_REGISTER_URL = (
    "https://services.arcgis.com/NzlPQPKn5QF9v2US/arcgis/rest/services/"
    "IrishPlanningApplications/FeatureServer/0/query"
)
WEXFORD_WHERE = "PlanningAuthority = 'Wexford County Council'"


def download_wexford():
    records = arcgis_download(WEXFORD_URL, skip_sort=True, prefix="Wexford: ")
    council_details = arcgis_download(
        WEXFORD_DETAILS_URL,
        skip_sort=True,
        prefix="Wexford received dates: ",
    )
    register = arcgis_download(
        WEXFORD_REGISTER_URL,
        skip_sort=True,
        where=WEXFORD_WHERE,
        prefix="Wexford dates: ",
    )
    details_by_number = {
        str(record.get("ApplicationNumber")).strip().casefold(): record
        for record in register
        if record.get("ApplicationNumber") not in (None, "")
    }
    council_by_number = {
        str(number).strip().casefold(): record
        for record in council_details
        if (number := record.get("Planning_Number") or record.get("Plan_Ref"))
        not in (None, "")
    }
    objects = []
    for record in records:
        number = record.get("Planning_Number")
        details = (
            details_by_number.get(str(number).strip().casefold()) if number else None
        )
        council = (
            council_by_number.get(str(number).strip().casefold()) if number else None
        )
        objects.append(WexfordObject.parse(record, details, council))
    write_to_db(wexford_db, WexfordObject, objects)


class WexfordObject(Model):
    objid = IntegerField(unique=True)
    application_number = CharField(null=True, index=True)
    address = TextField()
    searchable_address = TextField()
    application_type = CharField(null=True)
    application_status = CharField(null=True)
    decision = CharField(null=True)
    description = TextField(null=True)
    received_date = IntegerField(null=True)
    decision_date = IntegerField(null=True)
    details_url = TextField(null=True)

    class Meta:
        database = wexford_database

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
    def parse(data, details=None, council_details=None):
        if isinstance(data, WexfordObject):
            return data
        details = details or {}
        council_details = council_details or {}
        return WexfordObject(
            objid=data.get("OBJECTID"),
            application_number=data.get("Planning_Number"),
            address=data.get("Address") or details.get("DevelopmentAddress") or "",
            application_type=details.get("ApplicationType")
            or council_details.get("App_Type"),
            application_status=details.get("ApplicationStatus")
            or council_details.get("Status_Desc"),
            decision=data.get("Thematic_Decision")
            or details.get("Decision")
            or council_details.get("Decision"),
            description=data.get("Description")
            or details.get("DevelopmentDescription")
            or council_details.get("Proposal"),
            received_date=details.get("ReceivedDate")
            or council_details.get("Reg_date"),
            decision_date=details.get("DecisionDate"),
            details_url=data.get("DirectLink2DMS") or details.get("LinkAppDetails"),
        )


class WexfordDB:
    def __init__(self):
        self.db = wexford_database
        self.db.connect(reuse_if_open=True)
        self.db.create_tables([WexfordObject])

    def __len__(self):
        return WexfordObject.select().count()

    def __iter__(self) -> Iterable[WexfordObject]:
        return WexfordObject.select().iterator()

    def recreate(self):
        self.db.drop_tables([WexfordObject], safe=True)
        self.db.create_tables([WexfordObject])

    def filter(
        self,
        address_substrs=None,
        exclude_address_substrs=None,
        address=None,
        partial=False,
    ) -> List[WexfordObject]:
        query = WexfordObject.select()
        if address:
            address = clean_address_for_comparison(address)
            if partial:
                query = query.where(WexfordObject.searchable_address.contains(address))
            else:
                query = query.where(WexfordObject.searchable_address == address)
        for value in address_substrs or []:
            query = query.where(
                WexfordObject.searchable_address.contains(
                    clean_address_for_comparison(value)
                )
            )
        for value in exclude_address_substrs or []:
            query = query.where(
                ~WexfordObject.searchable_address.contains(
                    clean_address_for_comparison(value)
                )
            )
        return list(query)


wexford_db = WexfordDB()
