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

from planning_permission.settings import DCC_DB_LOCATION
from planning_permission.utils import clean_address_for_comparison


class DCCObject(Model):
    objid = IntegerField()
    address = CharField()
    searchable_address = CharField()

    proposal = TextField(null=True)
    applicant_surname = CharField(null=True)
    applicant_prop_key = CharField(null=True)

    registration_date = DateField(null=True)
    decision_date = DateField(null=True)
    final_grant_date = DateField(null=True)
    extension_date = DateField(null=True)
    appeal_lodged_date = DateField(null=True)
    appeal_decision_date = DateField(null=True)
    appeal_notify_date = DateField(null=True)
    register_date = DateField(null=True)
    dispatch_date = DateField(null=True)
    statutory_expiry_date = DateField(null=True)
    decision_expiry_date = DateField(null=True)
    received_date = DateField(null=True)
    publicity_end_date = DateField(null=True)
    submission_expiry_date = DateField(null=True)
    application_date = DateField(null=True)
    decision_due_date = DateField(null=True)

    decision_text = CharField(null=True)
    abp_reference = CharField(null=True)
    appeal_decision = CharField(null=True)
    postcode = CharField(null=True)

    lat = FloatField(null=True)
    lng = FloatField(null=True)

    full_proposal = TextField(null=True)
    status_description = CharField(null=True)
    status_owner = CharField(null=True)
    status_non_owner = CharField(null=True)
    application_type_id = IntegerField(null=True)
    application_type = CharField(null=True)
    agent_surname = CharField(null=True)
    officer_name = CharField(null=True)
    appeal_type = CharField(null=True)
    comments_mode = CharField(null=True)
    uprn = CharField(null=True)
    agent_prop_key = CharField(null=True)
    property_id = IntegerField(null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.address = self.address.strip().replace(" ,", ",")
        while "  " in self.address:
            self.address = self.address.replace("  ", " ")

        if not self.searchable_address:
            self.searchable_address = self.compute_searchable_address()

    class Meta:
        database = SqliteDatabase(DCC_DB_LOCATION)

    def save(self, *args, **kwargs):
        self.searchable_address = self.compute_searchable_address()
        try:
            return super(DCCObject, self).save(*args, **kwargs)
        except IntegrityError:
            pass

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return f"{self.objid}: {self.address}"

    def compute_searchable_address(self) -> str:
        return clean_address_for_comparison(self.address)

    @staticmethod
    def parse(data):
        if isinstance(data, DCCObject):
            return data
        if isinstance(data, dict):
            data.pop(None, None)
        return DCCObject(**data)


class DCCDB:
    def __init__(self) -> None:
        self.create_connection()

    def __len__(self) -> int:
        return DCCObject.select().count()

    def __iter__(self) -> Iterable[DCCObject]:
        return DCCObject.select().iterator()

    def drop_data(self) -> None:
        DCCObject.delete().execute()

    def recreate(self) -> None:
        self.db.drop_tables([DCCObject], safe=True)
        self.db.create_tables([DCCObject])

    def create_connection(self) -> None:
        self.db = SqliteDatabase(DCC_DB_LOCATION)
        self.db.connect()
        self.db.create_tables([DCCObject])

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
    ) -> List[DCCObject]:
        filters = {}

        query = DCCObject.select()

        for field, value in filters.items():
            if value is not None:
                field_name = getattr(DCCObject, field)
                if partial:
                    query = query.where(field_name.ilike(f"%{value}%"))
                else:
                    query = query.where(field_name.ilike(value))

        if address:
            address = address.replace(" ", "").replace(",", "").lower()
            if partial:
                query = query.where(DCCObject.searchable_address.contains(address))
            else:
                query = query.where(DCCObject.searchable_address == address)

        if address_substrs:
            for address_substr in address_substrs:
                query = query.where(
                    DCCObject.searchable_address.contains(
                        clean_address_for_comparison(address_substr)
                    )
                )

        if exclude_address_substrs:
            for exclude_address_substr in exclude_address_substrs:
                query = query.where(
                    ~(
                        DCCObject.searchable_address.contains(
                            clean_address_for_comparison(exclude_address_substr)
                        )
                    )
                )

        return [obj for obj in query]


dcc_db = DCCDB()
