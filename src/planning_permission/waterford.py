from typing import Iterable, List

from peewee import CharField, FloatField, IntegerField, Model, SqliteDatabase, TextField

from planning_permission.settings import WATERFORD_DB_LOCATION
from planning_permission.utils import clean_address_for_comparison
from planning_permission.utils import write_to_db, arcgis_download


WATERFORD_URL = "https://services-eu1.arcgis.com/eivETUtIaP8x2Pdh/arcgis/rest/services/PlanningApplicationRegisterPublicNew_view/FeatureServer/2/query"
waterford_database = SqliteDatabase(WATERFORD_DB_LOCATION)


def download_waterford():
    objects = [
        WaterfordObject.parse(record)
        for record in arcgis_download(
            WATERFORD_URL, skip_sort=True, prefix="Waterford: "
        )
    ]
    write_to_db(waterford_db, WaterfordObject, objects)


class WaterfordObject(Model):
    objid = IntegerField(unique=True)
    application_number = CharField(index=True)
    address = TextField(default="")
    searchable_address = TextField(default="")
    planning_authority = CharField(null=True)
    application_status = CharField(null=True)
    application_type = CharField(null=True)
    applicant_name = CharField(null=True)
    description = TextField(null=True)
    decision = CharField(null=True)
    received_date = CharField(null=True)
    decision_date = CharField(null=True)
    decision_due_date = CharField(null=True)
    appeal_decision = CharField(null=True)
    appeal_decision_date = CharField(null=True)
    link_app_details = TextField(null=True)
    link_app_documents = TextField(null=True)
    itm_easting = FloatField(null=True)
    itm_northing = FloatField(null=True)
    source_updated_date = IntegerField(null=True)

    class Meta:
        database = waterford_database

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.address = " ".join((self.address or "").split())
        if not self.searchable_address:
            self.searchable_address = self.compute_searchable_address()

    def compute_searchable_address(self):
        return clean_address_for_comparison(self.address)

    def save(self, *args, **kwargs):
        self.searchable_address = self.compute_searchable_address()
        return super().save(*args, **kwargs)

    @staticmethod
    def parse(data):
        if isinstance(data, WaterfordObject):
            return data
        return WaterfordObject(
            objid=data.get("OBJECTID"),
            application_number=data.get("ApplicationNumber"),
            address=data.get("Location") or "",
            planning_authority=data.get("PlanningAuthority"),
            application_status=data.get("ApplicationStatus"),
            application_type=data.get("ApplicationType"),
            applicant_name=data.get("ApplicantName"),
            description=data.get("Description"),
            decision=data.get("Decision"),
            received_date=data.get("ReceivedDate"),
            decision_date=data.get("DecisionDate"),
            decision_due_date=data.get("DecisionDueDate"),
            appeal_decision=data.get("AppealDecision"),
            appeal_decision_date=data.get("AppealDecisionDate"),
            link_app_details=data.get("LinkAppDetails"),
            link_app_documents=data.get("LinkAppDocuments"),
            itm_easting=data.get("ITMEasting"),
            itm_northing=data.get("ITMNorthing"),
            source_updated_date=data.get("fme_datecreated"),
        )


class WaterfordDB:
    def __init__(self):
        self.db = waterford_database
        self.db.connect(reuse_if_open=True)
        self.db.create_tables([WaterfordObject])

    def __len__(self):
        return WaterfordObject.select().count()

    def __iter__(self) -> Iterable[WaterfordObject]:
        return WaterfordObject.select().iterator()

    def recreate(self):
        self.db.drop_tables([WaterfordObject], safe=True)
        self.db.create_tables([WaterfordObject])

    def filter(
        self,
        address_substrs=None,
        exclude_address_substrs=None,
        address=None,
        partial=False,
    ) -> List[WaterfordObject]:
        query = WaterfordObject.select()
        if address:
            value = clean_address_for_comparison(address)
            query = query.where(
                WaterfordObject.searchable_address.contains(value)
                if partial
                else WaterfordObject.searchable_address == value
            )
        for value in address_substrs or []:
            query = query.where(
                WaterfordObject.searchable_address.contains(
                    clean_address_for_comparison(value)
                )
            )
        for value in exclude_address_substrs or []:
            query = query.where(
                ~WaterfordObject.searchable_address.contains(
                    clean_address_for_comparison(value)
                )
            )
        return list(query)


waterford_db = WaterfordDB()
