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

from planning_permission.settings import GALWAY_DB_LOCATION
from planning_permission.utils import clean_address_for_comparison


class GalwayObject(Model):
    objid = IntegerField(null=True)
    address = CharField()
    searchable_address = CharField()

    application_number = CharField(null=True)
    applicant_name = CharField(null=True)
    application_type = CharField(null=True)
    application_status = CharField(null=True)
    description = TextField(null=True)
    decision = CharField(null=True)

    received_date = CharField(null=True)
    withdrawn_date = CharField(null=True)
    grant_date = CharField(null=True)
    expiry_date = CharField(null=True)
    decision_date = CharField(null=True)
    decision_due_date = CharField(null=True)

    appeal_notification_date = CharField(null=True)
    appeal_ref_num = CharField(null=True)
    appeal_decision = CharField(null=True)
    appeal_decision_date = CharField(null=True)

    lat = FloatField(null=True)
    lng = FloatField(null=True)
    more_info = CharField(null=True)
    global_id = CharField(null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.address = self.address.strip().replace(" ,", ",")
        while "  " in self.address:
            self.address = self.address.replace("  ", " ")

        if not self.searchable_address:
            self.searchable_address = self.compute_searchable_address()

    class Meta:
        database = SqliteDatabase(GALWAY_DB_LOCATION)

    def save(self, *args, **kwargs):
        self.searchable_address = self.compute_searchable_address()
        try:
            return super(GalwayObject, self).save(*args, **kwargs)
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
        if isinstance(data, GalwayObject):
            return data
        if isinstance(data, dict):
            data.pop(None, None)
        return GalwayObject(**data)


class GalwayDB:
    def __init__(self) -> None:
        self.create_connection()

    def __len__(self) -> int:
        return GalwayObject.select().count()

    def __iter__(self) -> Iterable[GalwayObject]:
        return GalwayObject.select().iterator()

    def drop_data(self) -> None:
        GalwayObject.delete().execute()

    def recreate(self) -> None:
        self.db.drop_tables([GalwayObject], safe=True)
        self.db.create_tables([GalwayObject])

    def create_connection(self) -> None:
        self.db = SqliteDatabase(GALWAY_DB_LOCATION)
        self.db.connect()
        self.db.create_tables([GalwayObject])

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
    ) -> List[GalwayObject]:
        filters = {}

        query = GalwayObject.select()

        for field, value in filters.items():
            if value is not None:
                field_name = getattr(GalwayObject, field)
                if partial:
                    query = query.where(field_name.ilike(f"%{value}%"))
                else:
                    query = query.where(field_name.ilike(value))

        if address:
            address = address.replace(" ", "").replace(",", "").lower()
            if partial:
                query = query.where(GalwayObject.searchable_address.contains(address))
            else:
                query = query.where(GalwayObject.searchable_address == address)

        if address_substrs:
            for address_substr in address_substrs:
                query = query.where(
                    GalwayObject.searchable_address.contains(
                        clean_address_for_comparison(address_substr)
                    )
                )

        if exclude_address_substrs:
            for exclude_address_substr in exclude_address_substrs:
                query = query.where(
                    ~(
                        GalwayObject.searchable_address.contains(
                            clean_address_for_comparison(exclude_address_substr)
                        )
                    )
                )

        return [obj for obj in query]


galway_db = GalwayDB()
