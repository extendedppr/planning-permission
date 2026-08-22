from typing import Iterable, List

from peewee import (
    Model,
    TextField,
    IntegerField,
    CharField,
    SqliteDatabase,
    IntegrityError,
)

from planning_permission.settings import MEATH_DB_LOCATION
from planning_permission.utils import (
    clean_address_for_comparison,
    arcgis_download,
    write_to_db,
)

meath_database = SqliteDatabase(MEATH_DB_LOCATION)

MEATH_URL = (
    "https://services-eu1.arcgis.com/33tCl0taHHdVAN9O/"
    "arcgis/rest/services/DM_PACE_PlanningApplicationPublic/"
    "FeatureServer/0/query"
)


def download_meath():
    objects = [
        MeathObject.parse(record)
        for record in arcgis_download(MEATH_URL, skip_sort=True, prefix="Meath: ")
    ]
    write_to_db(meath_db, MeathObject, objects)


class MeathObject(Model):
    objid = IntegerField(unique=True)
    application_number = CharField(unique=True)
    address = CharField()
    searchable_address = CharField()

    planning_authority = CharField(null=True)
    applicant_name = CharField(null=True)
    application_status = CharField(null=True)
    description = TextField(null=True)
    decision = CharField(null=True)

    received_date = IntegerField(null=True)
    decision_date = IntegerField(null=True)

    address_line_1 = CharField(null=True)
    address_line_2 = CharField(null=True)
    address_line_3 = CharField(null=True)
    link_scanned_documents = TextField(null=True)
    link_eplanning = TextField(null=True)
    global_id = CharField(null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.address = self.address.strip().replace(" ,", ",")
        while "  " in self.address:
            self.address = self.address.replace("  ", " ")

        if not self.searchable_address:
            self.searchable_address = self.compute_searchable_address()

    class Meta:
        database = meath_database

    def save(self, *args, **kwargs):
        self.searchable_address = self.compute_searchable_address()
        try:
            return super(MeathObject, self).save(*args, **kwargs)
        except IntegrityError:
            pass

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return f"{self.application_number}: {self.address}"

    def compute_searchable_address(self) -> str:
        return clean_address_for_comparison(self.address)

    @staticmethod
    def parse(data):
        if isinstance(data, MeathObject):
            return data
        if isinstance(data, dict):
            data = data.copy()
            data.pop(None, None)
            field_map = {
                "OBJECTID": "objid",
                "PlanningAuthority": "planning_authority",
                "PlanningReference": "application_number",
                "Decision": "decision",
                "RecievedDate": "received_date",
                "DecisionDate": "decision_date",
                "Applicant": "applicant_name",
                "ApplicationStatus": "application_status",
                "DevelopmentDescription": "description",
                "Address_Line1": "address_line_1",
                "Address_Line2": "address_line_2",
                "Address_Line3": "address_line_3",
                "LinktoScannedDocuments": "link_scanned_documents",
                "LinktoePlan": "link_eplanning",
                "GlobalID": "global_id",
            }
            data = {field_map.get(key, key): value for key, value in data.items()}
            data.setdefault(
                "address",
                ", ".join(
                    value
                    for value in (
                        data.get("address_line_1"),
                        data.get("address_line_2"),
                        data.get("address_line_3"),
                    )
                    if value
                ),
            )
            data = {
                key: value
                for key, value in data.items()
                if key in MeathObject._meta.fields
            }
        return MeathObject(**data)


class MeathDB:
    def __init__(self) -> None:
        self.create_connection()

    def __len__(self) -> int:
        return MeathObject.select().count()

    def __iter__(self) -> Iterable[MeathObject]:
        return MeathObject.select().iterator()

    def drop_data(self) -> None:
        MeathObject.delete().execute()

    def recreate(self) -> None:
        self.db.drop_tables([MeathObject], safe=True)
        self.db.create_tables([MeathObject])

    def create_connection(self) -> None:
        self.db = meath_database
        self.db.connect(reuse_if_open=True)
        self.db.create_tables([MeathObject])

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
    ) -> List[MeathObject]:
        filters = {}

        query = MeathObject.select()

        for field, value in filters.items():
            if value is not None:
                field_name = getattr(MeathObject, field)
                if partial:
                    query = query.where(field_name.ilike(f"%{value}%"))
                else:
                    query = query.where(field_name.ilike(value))

        if address:
            address = address.replace(" ", "").replace(",", "").lower()
            if partial:
                query = query.where(MeathObject.searchable_address.contains(address))
            else:
                query = query.where(MeathObject.searchable_address == address)

        if address_substrs:
            for address_substr in address_substrs:
                query = query.where(
                    MeathObject.searchable_address.contains(
                        clean_address_for_comparison(address_substr)
                    )
                )

        if exclude_address_substrs:
            for exclude_address_substr in exclude_address_substrs:
                query = query.where(
                    ~(
                        MeathObject.searchable_address.contains(
                            clean_address_for_comparison(exclude_address_substr)
                        )
                    )
                )

        return [obj for obj in query]


meath_db = MeathDB()
