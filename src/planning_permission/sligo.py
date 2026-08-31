import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import progressbar
import requests

from planning_permission.local_register import create_local_download
from planning_permission.mayo import _mayo_request, _parse_mayo_detail
from planning_permission.settings import SLIGO_DB_LOCATION
from planning_permission.utils import arcgis_download, write_to_db

SLIGO_URL = "https://services-eu1.arcgis.com/jgNFn6b1W4PAHceK/arcgis/rest/services/Public_Planning_Apps_View/FeatureServer/2/query"
SLIGO_DETAIL_URL = "https://www.eplanning.ie/SligoCC/AppFileRefDetails/{}/0"
SLIGO_REQUEST_WORKERS = 10

SligoObject, sligo_db, _download_sligo_gis = create_local_download(
    "sligo", "Sligo County Council", SLIGO_DB_LOCATION, (("register", SLIGO_URL),)
)


def get_all_sligo_applications():
    source_records = {}
    for record in arcgis_download(SLIGO_URL, skip_sort=True, prefix="Sligo register: "):
        if number := record.get("ApplicationNumber"):
            source_records[str(number).strip().casefold()] = record

    local = threading.local()

    def get_application(reference):
        if not hasattr(local, "session"):
            local.session = requests.Session()
        details_url = SLIGO_DETAIL_URL.format(reference)
        try:
            response = _mayo_request(local.session, "GET", details_url)
            response.raise_for_status()
        except requests.RequestException:
            return None
        return _parse_mayo_detail(
            response.text,
            details_url,
            planning_authority="Sligo County Council",
        )

    records = []
    bar = progressbar.ProgressBar(
        max_value=len(source_records), prefix="Sligo details: "
    )
    with ThreadPoolExecutor(max_workers=SLIGO_REQUEST_WORKERS) as executor:
        futures = {
            executor.submit(get_application, reference): record
            for reference, record in source_records.items()
        }
        for completed, future in enumerate(as_completed(futures), 1):
            fallback = futures[future]
            records.append(future.result() or fallback)
            bar.update(completed)
    bar.finish()
    return records


def download_sligo():
    objects = [
        SligoObject.parse(record, "Sligo County Council")
        for record in get_all_sligo_applications()
    ]
    write_to_db(sligo_db, SligoObject, [obj for obj in objects if obj])
