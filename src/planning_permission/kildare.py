import math
import string
from typing import Iterable, List

import progressbar
from peewee import (
    Model,
    TextField,
    IntegerField,
    CharField,
    SqliteDatabase,
    IntegrityError,
    chunked,
)

from planning_permission.settings import KILDARE_DB_LOCATION
from planning_permission.utils import clean_address_for_comparison, get

kildare_database = SqliteDatabase(KILDARE_DB_LOCATION)


def download_kildare():
    base_url = "https://webgeo.kildarecoco.ie/planningenquiry/Public/GetPlanningFileNameAddressResult?name=&address={letter}&devDesc=&startDate=&endDate="

    kildare_db.drop_data()

    objects = []
    application_numbers = set()
    for letter in progressbar.progressbar(
        list(reversed(string.ascii_lowercase)), prefix="Kildare: "
    ):
        url = base_url.format(letter=letter)

        response = get(url)

        for obj_dict in response.json():
            obj = KildareObject.parse(obj_dict)
            if obj.application_number not in application_numbers:
                objects.append(obj)
                application_numbers.add(obj.application_number)

    batch_size = 500
    total_batches = math.ceil(len(objects) / batch_size)
    print(f"About to insert {len(objects)} objects into the database")

    with kildare_db.db.atomic():
        for batch in progressbar.progressbar(
            chunked(objects, batch_size),
            max_value=total_batches,
            prefix="Kildare: ",
        ):
            KildareObject.bulk_create(batch, batch_size=batch_size)


class KildareObject(Model):
    application_number = CharField(unique=True)
    address = CharField()
    searchable_address = CharField()

    planning_authority = CharField(null=True)
    applicant_name = CharField(null=True)
    application_type = CharField(null=True)
    application_status = CharField(null=True)
    description = TextField(null=True)
    development_address = TextField(null=True)
    decision = CharField(null=True)

    received_date = CharField(null=True)
    submissions_by = CharField(null=True)
    decision_due_date = CharField(null=True)
    decision_date = CharField(null=True)
    grant_date = CharField(null=True)
    further_info_requested = CharField(null=True)
    further_info_received = CharField(null=True)
    report_file_location = TextField(null=True)
    engineering_area = IntegerField(null=True)
    planner = CharField(null=True)
    number_of_appeals = CharField(null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.address = self.address.strip().replace(" ,", ",")
        while "  " in self.address:
            self.address = self.address.replace("  ", " ")

        if not self.searchable_address:
            self.searchable_address = self.compute_searchable_address()

    class Meta:
        database = kildare_database

    def save(self, *args, **kwargs):
        self.searchable_address = self.compute_searchable_address()
        try:
            return super(KildareObject, self).save(*args, **kwargs)
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
        if isinstance(data, KildareObject):
            return data
        if isinstance(data, dict):
            data = data.copy()
            data.pop(None, None)
            field_map = {
                "FileNumber": "application_number",
                "LocalAuthority": "planning_authority",
                "DateReceived": "received_date",
                "Type": "application_type",
                "SubmissionsBy": "submissions_by",
                "DueDate": "decision_due_date",
                "Decision": "decision",
                "DecisionDateMO": "decision_date",
                "ApplicationStatus": "application_status",
                "GrantDate": "grant_date",
                "FurtherInfoRequested": "further_info_requested",
                "FurtherInfoReceived": "further_info_received",
                "ReportFileLocation": "report_file_location",
                "ApplicantName": "applicant_name",
                "DevelopmentDescription": "description",
                "DevelopmentAddress": "development_address",
                "EngineeringArea": "engineering_area",
                "Planner": "planner",
                "NumberofAppealstoAnBordPleanala": "number_of_appeals",
            }
            data = {field_map.get(key, key): value for key, value in data.items()}
            data.setdefault("address", data.get("development_address") or "")
        return KildareObject(**data)


class KildareDB:
    def __init__(self) -> None:
        self.create_connection()

    def __len__(self) -> int:
        return KildareObject.select().count()

    def __iter__(self) -> Iterable[KildareObject]:
        return KildareObject.select().iterator()

    def drop_data(self) -> None:
        KildareObject.delete().execute()

    def recreate(self) -> None:
        self.db.drop_tables([KildareObject], safe=True)
        self.db.create_tables([KildareObject])

    def create_connection(self) -> None:
        self.db = kildare_database
        self.db.connect(reuse_if_open=True)
        self.db.create_tables([KildareObject])

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
    ) -> List[KildareObject]:
        filters = {}

        query = KildareObject.select()

        for field, value in filters.items():
            if value is not None:
                field_name = getattr(KildareObject, field)
                if partial:
                    query = query.where(field_name.ilike(f"%{value}%"))
                else:
                    query = query.where(field_name.ilike(value))

        if address:
            address = address.replace(" ", "").replace(",", "").lower()
            if partial:
                query = query.where(KildareObject.searchable_address.contains(address))
            else:
                query = query.where(KildareObject.searchable_address == address)

        if address_substrs:
            for address_substr in address_substrs:
                query = query.where(
                    KildareObject.searchable_address.contains(
                        clean_address_for_comparison(address_substr)
                    )
                )

        if exclude_address_substrs:
            for exclude_address_substr in exclude_address_substrs:
                query = query.where(
                    ~(
                        KildareObject.searchable_address.contains(
                            clean_address_for_comparison(exclude_address_substr)
                        )
                    )
                )

        return [obj for obj in query]


kildare_db = KildareDB()
