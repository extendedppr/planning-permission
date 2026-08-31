import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import progressbar
import requests

from planning_permission.local_register import create_local_download
from planning_permission.mayo import _mayo_request, _parse_mayo_detail
from planning_permission.settings import LEITRIM_DB_LOCATION
from planning_permission.utils import arcgis_download, write_to_db

LEITRIM_URLS = (
    (
        "2000-2022",
        "https://services7.arcgis.com/EhwGJvRfdoo8Udzk/arcgis/rest/services/AllPlanningApplications/FeatureServer/0/query",
    ),
    (
        "newer sites",
        "https://services7.arcgis.com/EhwGJvRfdoo8Udzk/arcgis/rest/services/Post_2022_PLApplics/FeatureServer/0/query",
    ),
)
LEITRIM_DETAIL_URL = "https://www.eplanning.ie/LeitrimCC/AppFileRefDetails/{}/0"
LEITRIM_REQUEST_WORKERS = 10

LeitrimObject, leitrim_db, _download_leitrim_gis = create_local_download(
    "leitrim", "Leitrim County Council", LEITRIM_DB_LOCATION, LEITRIM_URLS
)


def _compact_reference(record):
    if record.get("file_year") and record.get("file_num"):
        return f"{str(record['file_year']).strip()}{str(record['file_num']).strip()}"
    return (
        str(
            record.get("FILENUMB_1")
            or record.get("FileNumber")
            or record.get("FILENUMBER")
            or ""
        )
        .replace("/", "")
        .strip()
    )


def get_all_leitrim_applications():
    source_records = {}
    for label, url in LEITRIM_URLS:
        for record in arcgis_download(url, skip_sort=True, prefix=f"Leitrim {label}: "):
            if reference := _compact_reference(record):
                source_records[reference.casefold()] = record

    local = threading.local()

    def get_application(reference):
        if not hasattr(local, "session"):
            local.session = requests.Session()
        details_url = LEITRIM_DETAIL_URL.format(reference)
        try:
            response = _mayo_request(local.session, "GET", details_url)
            response.raise_for_status()
        except requests.RequestException:
            return None
        return _parse_mayo_detail(
            response.text,
            details_url,
            planning_authority="Leitrim County Council",
        )

    records = []
    bar = progressbar.ProgressBar(
        max_value=len(source_records), prefix="Leitrim details: "
    )
    with ThreadPoolExecutor(max_workers=LEITRIM_REQUEST_WORKERS) as executor:
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


def download_leitrim():
    objects = [
        LeitrimObject.parse(record, "Leitrim County Council")
        for record in get_all_leitrim_applications()
    ]
    write_to_db(leitrim_db, LeitrimObject, [obj for obj in objects if obj])
