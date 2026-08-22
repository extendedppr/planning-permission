from typing import Iterable, List

from peewee import CharField, IntegerField, Model, SqliteDatabase, TextField

from planning_permission.settings import TIPPERARY_DB_LOCATION
from planning_permission.utils import (
    clean_address_for_comparison,
    arcgis_download,
    write_to_db,
)


tipperary_database = SqliteDatabase(TIPPERARY_DB_LOCATION)
TIPPERARY_URL = "https://services-eu1.arcgis.com/1cOXMgl48vVRhreT/arcgis/rest/services/TCC_PlanningPublicView/FeatureServer/0/query"
TIPPERARY_REGISTER_URL = (
    "https://services.arcgis.com/NzlPQPKn5QF9v2US/arcgis/rest/services/"
    "IrishPlanningApplications/FeatureServer/0/query"
)
TIPPERARY_WHERE = "PlanningAuthority = 'Tipperary County Council'"


def download_tipperary():
    records = arcgis_download(TIPPERARY_URL, skip_sort=True, prefix="Tipperary: ")
    register = arcgis_download(
        TIPPERARY_REGISTER_URL,
        skip_sort=True,
        where=TIPPERARY_WHERE,
        prefix="Tipperary dates: ",
    )
    details_by_number = {
        str(record.get("ApplicationNumber")).strip().casefold(): record
        for record in register
        if record.get("ApplicationNumber") not in (None, "")
    }
    objects = []
    for record in records:
        number = record.get("FileNumber")
        details = (
            details_by_number.get(str(number).strip().casefold()) if number else None
        )
        objects.append(TipperaryObject.parse(record, details))
    write_to_db(tipperary_db, TipperaryObject, objects)


class TipperaryObject(Model):
    objid = IntegerField(unique=True)
    application_number = CharField(index=True)
    address = TextField()
    searchable_address = TextField()

    applicant_name = CharField(null=True)
    application_type = CharField(null=True)
    application_status = CharField(null=True)
    description = TextField(null=True)
    decision = CharField(null=True)
    status = CharField(null=True)
    received_date = IntegerField(null=True)
    decision_date = IntegerField(null=True)
    decision_manager_order_date = IntegerField(null=True)
    appeal_date = IntegerField(null=True)
    appeal_decision = CharField(null=True)
    protected_structure = CharField(null=True)
    part_5 = CharField(null=True)
    section_47 = CharField(null=True)
    eplanning_link = TextField(null=True)
    google_maps_link = TextField(null=True)
    street_view_link = TextField(null=True)
    global_id = CharField(null=True)

    class Meta:
        database = tipperary_database

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
    def parse(data, details=None):
        if isinstance(data, TipperaryObject):
            return data
        details = details or {}

        parsed = {
            "objid": data.get("OBJECTID"),
            "application_number": data.get("FileNumber"),
            "address": data.get("location_key") or "",
            "applicant_name": " ".join(
                value for value in (data.get("forename"), data.get("surname")) if value
            ),
            "application_type": data.get("application_type")
            or data.get("ApplicationType"),
            "application_status": data.get("application_status"),
            "description": data.get("development_descri"),
            "decision": data.get("DECISION"),
            "status": data.get("Status"),
            "received_date": details.get("ReceivedDate"),
            "decision_date": data.get("decision_date") or details.get("DecisionDate"),
            "decision_manager_order_date": data.get("decision_m_o_date"),
            "appeal_date": data.get("Appeal_Date"),
            "appeal_decision": data.get("Appeal_Decision"),
            "protected_structure": data.get("protected_struct_flag"),
            "part_5": data.get("part_5_flag"),
            "section_47": data.get("section_47_flag"),
            "eplanning_link": data.get("ePlan_Link"),
            "google_maps_link": data.get("GoogleMaps_Link"),
            "street_view_link": data.get("StreetView_Link"),
            "global_id": data.get("GlobalID"),
        }
        return TipperaryObject(**parsed)


class TipperaryDB:
    def __init__(self):
        self.db = tipperary_database
        self.db.connect(reuse_if_open=True)
        self.db.create_tables([TipperaryObject])

    def __len__(self):
        return TipperaryObject.select().count()

    def __iter__(self) -> Iterable[TipperaryObject]:
        return TipperaryObject.select().iterator()

    def recreate(self):
        self.db.drop_tables([TipperaryObject], safe=True)
        self.db.create_tables([TipperaryObject])

    def filter(
        self,
        address_substrs=None,
        exclude_address_substrs=None,
        address=None,
        partial=False,
    ) -> List[TipperaryObject]:
        query = TipperaryObject.select()
        if address:
            address = clean_address_for_comparison(address)
            if partial:
                query = query.where(
                    TipperaryObject.searchable_address.contains(address)
                )
            else:
                query = query.where(TipperaryObject.searchable_address == address)
        for value in address_substrs or []:
            query = query.where(
                TipperaryObject.searchable_address.contains(
                    clean_address_for_comparison(value)
                )
            )
        for value in exclude_address_substrs or []:
            query = query.where(
                ~TipperaryObject.searchable_address.contains(
                    clean_address_for_comparison(value)
                )
            )
        return list(query)


tipperary_db = TipperaryDB()
