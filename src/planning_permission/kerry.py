from typing import Iterable, List

from peewee import CharField, FloatField, IntegerField, Model, SqliteDatabase, TextField

from planning_permission.settings import KERRY_DB_LOCATION
from planning_permission.utils import (
    clean_address_for_comparison,
    arcgis_download,
    write_to_db,
)


kerry_database = SqliteDatabase(KERRY_DB_LOCATION)


KERRY_URL = "https://services2.arcgis.com/FQ08czOaoVds3IE4/arcgis/rest/services/paceJoinFS/FeatureServer/0/query"


def download_kerry():
    objects = [
        KerryObject.parse(record)
        for record in arcgis_download(KERRY_URL, skip_sort=True, prefix="Kerry: ")
    ]
    write_to_db(kerry_db, KerryObject, objects)


class KerryObject(Model):
    objid = IntegerField(unique=True)
    application_number = CharField(unique=True)
    address = TextField()
    searchable_address = TextField()

    applicant_name = CharField(null=True)
    application_type = CharField(null=True)
    application_status = CharField(null=True)
    description = TextField(null=True)
    decision = CharField(null=True)
    decision_description = TextField(null=True)
    received_date = CharField(null=True)
    pace_received_date = IntegerField(null=True)
    submissions_by = CharField(null=True)
    decision_due_date = CharField(null=True)
    decision_date = CharField(null=True)
    further_info_requested = CharField(null=True)
    further_info_received = CharField(null=True)
    site_id = FloatField(null=True)
    created_date = IntegerField(null=True)
    last_edited_date = IntegerField(null=True)
    shape_area = FloatField(null=True)
    shape_length = FloatField(null=True)

    class Meta:
        database = kerry_database

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
        if isinstance(data, KerryObject):
            return data
        prefix = "arcgis_sde_PES_Points_and_iPLAN_All_PlanDB_"
        return KerryObject(
            objid=data.get("OBJECTID"),
            application_number=(
                data.get(f"{prefix}Planning_Number") or data.get("PaceDL_FileNumber")
            ),
            address=data.get(f"{prefix}Development_Address") or "",
            applicant_name=data.get(f"{prefix}Applicant_Name"),
            application_type=data.get("PaceDL_ApplicationType"),
            application_status=data.get(f"{prefix}Application_Status"),
            description=data.get(f"{prefix}Development_Descripti"),
            decision=data.get(f"{prefix}Decision"),
            decision_description=data.get(f"{prefix}decision_description"),
            received_date=data.get(f"{prefix}Date_Received"),
            pace_received_date=data.get("PaceDL_ReceivedDate"),
            submissions_by=data.get(f"{prefix}Submissions_By"),
            decision_due_date=data.get(f"{prefix}Decision_Due_Date"),
            decision_date=data.get(f"{prefix}Decision_Date_MO"),
            further_info_requested=data.get(f"{prefix}Further_Info_Requeste"),
            further_info_received=data.get(f"{prefix}Further_Info_Received"),
            site_id=data.get("PaceDL_SiteID"),
            created_date=data.get("PaceDL_created_date"),
            last_edited_date=data.get("PaceDL_last_edited_date"),
            shape_area=data.get("Shape__Area"),
            shape_length=data.get("Shape__Length"),
        )


class KerryDB:
    def __init__(self):
        self.db = kerry_database
        self.db.connect(reuse_if_open=True)
        self.db.create_tables([KerryObject])

    def __len__(self):
        return KerryObject.select().count()

    def __iter__(self) -> Iterable[KerryObject]:
        return KerryObject.select().iterator()

    def recreate(self):
        self.db.drop_tables([KerryObject], safe=True)
        self.db.create_tables([KerryObject])

    def filter(
        self,
        address_substrs=None,
        exclude_address_substrs=None,
        address=None,
        partial=False,
    ) -> List[KerryObject]:
        query = KerryObject.select()
        if address:
            address = clean_address_for_comparison(address)
            query = query.where(
                KerryObject.searchable_address.contains(address)
                if partial
                else KerryObject.searchable_address == address
            )
        for value in address_substrs or []:
            query = query.where(
                KerryObject.searchable_address.contains(
                    clean_address_for_comparison(value)
                )
            )
        for value in exclude_address_substrs or []:
            query = query.where(
                ~KerryObject.searchable_address.contains(
                    clean_address_for_comparison(value)
                )
            )
        return list(query)


kerry_db = KerryDB()
