from typing import Iterable, List

from peewee import (
    Model,
    TextField,
    IntegerField,
    CharField,
    FloatField,
    SqliteDatabase,
    IntegrityError,
)

from planning_permission.settings import CORK_DB_LOCATION
from planning_permission.utils import clean_address_for_comparison


class CorkObject(Model):
    objid = IntegerField(null=True)
    address = CharField()
    searchable_address = CharField()

    planning_authority = CharField(null=True)
    applicant_name = CharField(null=True)
    application_number = CharField(null=True)
    application_type = CharField(null=True)
    application_status = CharField(null=True)
    description = TextField(null=True)
    development_address = TextField(null=True)
    decision = CharField(null=True)
    site_area = CharField(null=True)

    received_date = CharField(null=True)
    withdrawn_date = CharField(null=True)
    decision_due_date = CharField(null=True)
    decision_date = CharField(null=True)
    grant_date = CharField(null=True)
    expiry_date = CharField(null=True)
    appeal_submitted_date = CharField(null=True)
    appeal_decision_date = CharField(null=True)
    fi_request_date = CharField(null=True)
    fi_received_date = CharField(null=True)
    submission_date = CharField(null=True)

    file_year = IntegerField(null=True)
    appeal_ref_number = CharField(null=True)
    appeal_decision = CharField(null=True)
    appeal_type = CharField(null=True)
    fi_file_number = CharField(null=True)
    num_house_dev = IntegerField(null=True)
    number_floors = IntegerField(null=True)
    number_conditions = IntegerField(null=True)

    link_app_details = CharField(null=True)
    link_docs = CharField(null=True)
    link_docs_internal = CharField(null=True)
    global_id = CharField(null=True)
    shape_area = FloatField(null=True)
    shape_length = FloatField(null=True)
    geometry = TextField(null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.address = self.address.strip().replace(" ,", ",")
        while "  " in self.address:
            self.address = self.address.replace("  ", " ")

        if not self.searchable_address:
            self.searchable_address = self.compute_searchable_address()

    class Meta:
        database = SqliteDatabase(CORK_DB_LOCATION)

    def save(self, *args, **kwargs):
        self.searchable_address = self.compute_searchable_address()
        try:
            return super(CorkObject, self).save(*args, **kwargs)
        except IntegrityError:
            pass

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return f"{self.application_number or self.objid}: {self.address}"

    def compute_searchable_address(self) -> str:
        return clean_address_for_comparison(self.address)

    @staticmethod
    def parse(data):
        if isinstance(data, CorkObject):
            return data
        if isinstance(data, dict):
            data.pop(None, None)
        return CorkObject(**data)


class CorkDB:
    def __init__(self) -> None:
        self.create_connection()

    def __len__(self) -> int:
        return CorkObject.select().count()

    def __iter__(self) -> Iterable[CorkObject]:
        return CorkObject.select().iterator()

    def drop_data(self) -> None:
        CorkObject.delete().execute()

    def recreate(self) -> None:
        self.db.drop_tables([CorkObject], safe=True)
        self.db.create_tables([CorkObject])

    def create_connection(self) -> None:
        self.db = SqliteDatabase(CORK_DB_LOCATION)
        self.db.connect()
        self.db.create_tables([CorkObject])

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
    ) -> List[CorkObject]:
        filters = {}

        query = CorkObject.select()

        for field, value in filters.items():
            if value is not None:
                field_name = getattr(CorkObject, field)
                if partial:
                    query = query.where(field_name.ilike(f"%{value}%"))
                else:
                    query = query.where(field_name.ilike(value))

        if address:
            address = address.replace(" ", "").replace(",", "").lower()
            if partial:
                query = query.where(CorkObject.searchable_address.contains(address))
            else:
                query = query.where(CorkObject.searchable_address == address)

        if address_substrs:
            for address_substr in address_substrs:
                query = query.where(
                    CorkObject.searchable_address.contains(
                        clean_address_for_comparison(address_substr)
                    )
                )

        if exclude_address_substrs:
            for exclude_address_substr in exclude_address_substrs:
                query = query.where(
                    ~(
                        CorkObject.searchable_address.contains(
                            clean_address_for_comparison(exclude_address_substr)
                        )
                    )
                )

        return [obj for obj in query]


cork_db = CorkDB()
