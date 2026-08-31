import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable, List

import progressbar
import requests
from peewee import CharField, IntegerField, Model, SqliteDatabase, TextField

from planning_permission.mayo import _mayo_date, _mayo_request, _parse_mayo_detail
from planning_permission.settings import CLARE_DB_LOCATION
from planning_permission.utils import (
    arcgis_download,
    clean_address_for_comparison,
    write_to_db,
)


CLARE_SITES_URL = (
    "https://services8.arcgis.com/OnLILyV2xWhWjtPS/arcgis/rest/services/"
    "Planning_Applications_WFL1/FeatureServer/1/query"
)
CLARE_DETAIL_URL = "https://www.eplanning.ie/ClareCC/AppFileRefDetails/{}/0"
CLARE_REQUEST_WORKERS = 10
clare_database = SqliteDatabase(CLARE_DB_LOCATION)


def get_all_clare_applications():
    # This view advertises OBJECTID_1 but rejects it in orderByFields.
    sites = arcgis_download(CLARE_SITES_URL, skip_sort=True, prefix="Clare sites: ")
    sites_by_number = {
        str(site["FileNumber"]).strip().casefold(): site
        for site in sites
        if site.get("FileNumber") not in (None, "", "0")
    }
    local = threading.local()

    def get_application(number):
        if not hasattr(local, "session"):
            local.session = requests.Session()
        details_url = CLARE_DETAIL_URL.format(number)
        try:
            response = _mayo_request(local.session, "GET", details_url)
            response.raise_for_status()
        except requests.RequestException:
            return None
        return _parse_mayo_detail(
            response.text,
            details_url,
            planning_authority="Clare County Council",
        )

    records = []
    bar = progressbar.ProgressBar(
        max_value=len(sites_by_number), prefix="Clare details: "
    )
    with ThreadPoolExecutor(max_workers=CLARE_REQUEST_WORKERS) as executor:
        futures = {
            executor.submit(get_application, number): site
            for number, site in sites_by_number.items()
        }
        for completed, future in enumerate(as_completed(futures), 1):
            site = futures[future]
            records.append((site, future.result()))
            bar.update(completed)
    bar.finish()
    return records


def download_clare():
    objects = [
        ClareObject.parse(site, details)
        for site, details in get_all_clare_applications()
    ]
    write_to_db(clare_db, ClareObject, objects)


class ClareObject(Model):
    objid = IntegerField(unique=True)
    source_object_id = IntegerField(null=True)
    application_number = CharField(unique=True)
    address = TextField(default="")
    searchable_address = TextField(default="")
    planning_authority = CharField(null=True)
    application_type = CharField(null=True)
    application_status = CharField(null=True)
    description = TextField(null=True)
    decision = CharField(null=True)
    received_date = IntegerField(null=True)
    decision_date = IntegerField(null=True)
    site_id = CharField(null=True)
    details_url = TextField(null=True)

    class Meta:
        database = clare_database

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.address = (self.address or "").strip()
        if not self.searchable_address:
            self.searchable_address = clean_address_for_comparison(self.address)

    def save(self, *args, **kwargs):
        self.searchable_address = clean_address_for_comparison(self.address)
        return super().save(*args, **kwargs)

    @staticmethod
    def parse(data, details=None):
        if isinstance(data, ClareObject):
            return data
        details = details or {}
        return ClareObject(
            objid=data.get("OBJECTID_1") or data.get("OBJECTID"),
            source_object_id=data.get("OBJECTID"),
            application_number=data.get("FileNumber")
            or details.get("ApplicationNumber")
            or data.get("ApplicationNumber"),
            address=details.get("DevelopmentAddress") or "",
            planning_authority=details.get("PlanningAuthority"),
            application_type=data.get("ApplicationType")
            or details.get("ApplicationType"),
            application_status=details.get("ApplicationStatus"),
            description=details.get("DevelopmentDescription"),
            decision=details.get("Decision"),
            received_date=_mayo_date(details.get("ReceivedDate")),
            decision_date=_mayo_date(details.get("DecisionDate")),
            site_id=data.get("SiteID") or details.get("SiteId"),
            details_url=details.get("LinkAppDetails"),
        )


class ClareDB:
    def __init__(self):
        self.db = clare_database
        self.db.connect(reuse_if_open=True)
        self.db.create_tables([ClareObject])

    def __len__(self):
        return ClareObject.select().count()

    def __iter__(self) -> Iterable[ClareObject]:
        return ClareObject.select().iterator()

    def recreate(self):
        self.db.drop_tables([ClareObject], safe=True)
        self.db.create_tables([ClareObject])

    def filter(
        self,
        address_substrs=None,
        exclude_address_substrs=None,
        address=None,
        partial=False,
    ) -> List[ClareObject]:
        query = ClareObject.select()
        if address or address_substrs:
            return []
        return list(query)


clare_db = ClareDB()
