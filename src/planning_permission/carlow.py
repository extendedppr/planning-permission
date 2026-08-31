import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import progressbar
import requests

from planning_permission.local_register import create_local_download
from planning_permission.mayo import _mayo_request, _parse_mayo_detail
from planning_permission.settings import CARLOW_DB_LOCATION
from planning_permission.utils import arcgis_download, write_to_db

CARLOW_URL = "https://services.arcgis.com/8zunLZWYXqzwJUYx/arcgis/rest/services/Planning_Applications/FeatureServer/0/query"
CARLOW_DETAIL_URL = "https://www.eplanning.ie/CarlowCC/AppFileRefDetails/{}/0"
CARLOW_REQUEST_WORKERS = 10

CarlowObject, carlow_db, _download_carlow_gis = create_local_download(
    "carlow", "Carlow County Council", CARLOW_DB_LOCATION, (("register", CARLOW_URL),)
)


def get_all_carlow_applications():
    source_records = {}
    for record in arcgis_download(
        CARLOW_URL, skip_sort=True, prefix="Carlow register: "
    ):
        if number := record.get("Planning_R"):
            source_records[str(number).strip().casefold()] = record

    local = threading.local()

    def get_application(reference):
        if not hasattr(local, "session"):
            local.session = requests.Session()
        details_url = CARLOW_DETAIL_URL.format(reference)
        try:
            response = _mayo_request(local.session, "GET", details_url)
            response.raise_for_status()
        except requests.RequestException:
            return None
        return _parse_mayo_detail(
            response.text,
            details_url,
            planning_authority="Carlow County Council",
        )

    records = []
    bar = progressbar.ProgressBar(
        max_value=len(source_records), prefix="Carlow details: "
    )
    with ThreadPoolExecutor(max_workers=CARLOW_REQUEST_WORKERS) as executor:
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


def download_carlow():
    objects = [
        CarlowObject.parse(record, "Carlow County Council")
        for record in get_all_carlow_applications()
    ]
    write_to_db(carlow_db, CarlowObject, [obj for obj in objects if obj])
