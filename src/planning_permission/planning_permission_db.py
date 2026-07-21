from typing import Iterable, List

from peewee import (
    Model,
    TextField,
    IntegerField,
    DateField,
    CharField,
    FloatField,
    SqliteDatabase,
    IntegrityError,
)

from planning_permission.settings import PLANNING_PERMISSION_DB_LOCATION
from planning_permission.utils import is_nan, clean_address_for_comparison


class PlanningPermissionObject(Model):
    development_address = CharField()
    searchable_address = CharField()

    lat = FloatField(null=True)
    lng = FloatField(null=True)

    planning_authority = CharField()
    application_number = CharField()

    development_description = TextField()
    development_postcode = CharField(null=True)

    application_status = CharField()
    application_type = CharField()

    applicant_forename = CharField(null=True)
    applicant_surname = CharField(null=True)
    applicant_address = TextField(null=True)

    decision = CharField(null=True)
    land_use_code = CharField(null=True)

    area_of_site = FloatField(null=True)
    num_residential_units = IntegerField(default=0, null=True)

    one_off_house = CharField(null=True)

    floor_area = FloatField(null=True)

    received_date = DateField(null=True)
    withdrawn_date = DateField(null=True)
    decision_date = DateField(null=True)
    decision_due_date = DateField(null=True)
    grant_date = DateField(null=True)
    expiry_date = DateField(null=True)

    appeal_ref_number = CharField(null=True)
    appeal_status = CharField(null=True)
    appeal_decision = CharField(null=True)
    appeal_decision_date = DateField(null=True)
    appeal_submitted_date = DateField(null=True)

    fi_request_date = DateField(null=True)
    fi_rec_date = DateField(null=True)

    link_app_details = CharField(null=True)

    one_off_kpi = CharField(null=True)

    etl_date = DateField(null=True)

    site_id = IntegerField(null=True)
    orig_fid = IntegerField(null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.development_address = self.development_address.strip().replace(" ,", ",")
        while "  " in self.development_address:
            self.development_address = self.development_address.replace("  ", " ")

        if not self.searchable_address:
            self.searchable_address = self.compute_searchable_address()

    class Meta:
        database = SqliteDatabase(PLANNING_PERMISSION_DB_LOCATION)

    def save(self, *args, **kwargs):
        self.searchable_address = self.compute_searchable_address()
        try:
            return super(PlanningPermissionObject, self).save(*args, **kwargs)
        except IntegrityError:
            pass

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return f"{self.application_number}: {self.development_address}"

    def compute_searchable_address(self) -> str:
        return clean_address_for_comparison(self.development_address)

    @staticmethod
    def parse(data):
        if isinstance(data, PlanningPermissionObject):
            return data
        if isinstance(data, dict):
            data.pop(None, None)
        return PlanningPermissionObject(**data)

    @property
    def eircode_routing_key(self):
        if not is_nan(self.development_postcode):
            return self.development_postcode[:3].lower()
        return None

    @property
    def eircode_unique_id(self):
        if not is_nan(self.development_postcode):
            return self.development_postcode[3:].lower()
        return None


class PlanningPermissionDB:
    def __init__(self) -> None:
        self.create_connection()

    def __len__(self) -> int:
        return PlanningPermissionObject.select().count()

    def __iter__(self) -> Iterable[PlanningPermissionObject]:
        return PlanningPermissionObject.select().iterator()

    def drop_data(self) -> None:
        PlanningPermissionObject.delete().execute()

    def recreate(self) -> None:
        self.db.drop_tables([PlanningPermissionObject], safe=True)
        self.db.create_tables([PlanningPermissionObject])

    def create_connection(self) -> None:
        self.db = SqliteDatabase(PLANNING_PERMISSION_DB_LOCATION)
        self.db.connect()
        self.db.create_tables([PlanningPermissionObject])

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
    ) -> List[PlanningPermissionObject]:
        filters = {
            "development_postcode": eircode if eircode else None,
        }

        query = PlanningPermissionObject.select()

        for field, value in filters.items():
            if value is not None:
                field_name = getattr(PlanningPermissionObject, field)
                if partial:
                    query = query.where(field_name.ilike(f"%{value}%"))
                else:
                    query = query.where(field_name.ilike(value))

        if eircode_routing_key:
            query = query.where(
                PlanningPermissionObject.development_postcode.startswith(
                    eircode_routing_key
                )
            )

        if address:
            address = address.replace(" ", "").replace(",", "").lower()
            if partial:
                query = query.where(
                    PlanningPermissionObject.searchable_address.contains(address)
                )
            else:
                query = query.where(
                    PlanningPermissionObject.searchable_address == address
                )

        if address_substrs:
            for address_substr in address_substrs:
                query = query.where(
                    PlanningPermissionObject.searchable_address.contains(
                        clean_address_for_comparison(address_substr)
                    )
                )

        if exclude_address_substrs:
            for exclude_address_substr in exclude_address_substrs:
                query = query.where(
                    ~(
                        PlanningPermissionObject.searchable_address.contains(
                            clean_address_for_comparison(exclude_address_substr)
                        )
                    )
                )

        return [obj for obj in query]


planning_permission_db = PlanningPermissionDB()
