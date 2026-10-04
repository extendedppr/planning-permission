import math
from planning_permission.registry import COUNTIES as PLANNING_COUNTIES  # noqa: F401
from planning_permission.registry import REGISTRY
import re
from datetime import datetime
from functools import lru_cache
from math import atan, cos, degrees, isnan, radians, sin, sinh, sqrt, tan
from collections import defaultdict
from time import sleep

import progressbar
import requests
import backoff
import ujson
from playhouse.migrate import SqliteMigrator, migrate

from planning_permission.settings import (
    PLANNING_PERMISSION_LOCATION,
    SLEEP_BETWEEN_REQUESTS,
    INSERT_BATCH_SIZE,
)
from planning_permission.constants import DATA_URL


def read_json(filepath):
    # Do we need to iterate read since a big file?
    with open(filepath, "r") as fh:
        return ujson.loads(fh.read())


@lru_cache(maxsize=100)
def convert_date(date_str):
    if isinstance(date_str, datetime):
        return date_str

    if len(date_str) == 10:
        return datetime.strptime(date_str, "%d/%m/%Y")
    if len(date_str) == 19:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    else:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f")


def is_nan(value):
    return value is None or (isinstance(value, (float, int)) and isnan(value))


def web_mercator_to_lat_lng(x, y):
    if x is None or y is None:
        return None, None

    radius = 6378137.0
    lng = degrees(float(x) / radius)
    lat = degrees(atan(sinh(float(y) / radius)))
    return lat, lng


def itm_to_lat_lng(easting, northing):
    if easting is None or northing is None:
        return None, None

    a = 6378137.0
    f = 1 / 298.257222101
    b = a * (1 - f)
    e_sq = (a**2 - b**2) / a**2
    e_prime_sq = e_sq / (1 - e_sq)

    lat_origin = radians(53.5)
    lng_origin = radians(-8)
    false_easting = 600000.0
    false_northing = 750000.0
    scale = 0.99982

    e1 = (1 - sqrt(1 - e_sq)) / (1 + sqrt(1 - e_sq))

    def meridional_arc(lat):
        return a * (
            (1 - e_sq / 4 - 3 * e_sq**2 / 64 - 5 * e_sq**3 / 256) * lat
            - (3 * e_sq / 8 + 3 * e_sq**2 / 32 + 45 * e_sq**3 / 1024) * sin(2 * lat)
            + (15 * e_sq**2 / 256 + 45 * e_sq**3 / 1024) * sin(4 * lat)
            - (35 * e_sq**3 / 3072) * sin(6 * lat)
        )

    m_origin = meridional_arc(lat_origin)
    m = m_origin + (float(northing) - false_northing) / scale
    mu = m / (a * (1 - e_sq / 4 - 3 * e_sq**2 / 64 - 5 * e_sq**3 / 256))

    footpoint_lat = (
        mu
        + (3 * e1 / 2 - 27 * e1**3 / 32) * sin(2 * mu)
        + (21 * e1**2 / 16 - 55 * e1**4 / 32) * sin(4 * mu)
        + (151 * e1**3 / 96) * sin(6 * mu)
        + (1097 * e1**4 / 512) * sin(8 * mu)
    )

    sin_fp = sin(footpoint_lat)
    cos_fp = cos(footpoint_lat)
    tan_fp = tan(footpoint_lat)

    n1 = a / sqrt(1 - e_sq * sin_fp**2)
    r1 = a * (1 - e_sq) / (1 - e_sq * sin_fp**2) ** 1.5
    t1 = tan_fp**2
    c1 = e_prime_sq * cos_fp**2
    d = (float(easting) - false_easting) / (n1 * scale)

    lat = footpoint_lat - (n1 * tan_fp / r1) * (
        d**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * e_prime_sq) * d**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * e_prime_sq - 3 * c1**2)
        * d**6
        / 720
    )
    lng = (
        lng_origin
        + (
            d
            - (1 + 2 * t1 + c1) * d**3 / 6
            + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * e_prime_sq + 24 * t1**2)
            * d**5
            / 120
        )
        / cos_fp
    )

    return degrees(lat), degrees(lng)


def download_planning_permission():
    with requests.get(DATA_URL, stream=True, timeout=30) as response:
        response.raise_for_status()
        with open(PLANNING_PERMISSION_LOCATION, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)


def clean_address_for_comparison(address):
    return (
        address.lower()
        .replace(" ", "")
        .replace(".", "")
        .replace("'", "")
        .replace(",", "")
        .replace("(", "")
        .replace(")", "")
        .replace('"', "")
        .replace("'", "")
        .replace("county", "co")
        .replace("road", "rd")
        .replace("avenue", "ave")
        .replace("street", "st")
    )


def ngrams(text, count):
    text = re.sub(r"[^a-z]", "", text.lower())
    return {text[i : i + count] for i in range(len(text) - count + 1)}


def min_set_cover(addresses, count=2, use_precalculated=True):
    if use_precalculated:
        if count == 2:
            return [
                # "co",
                "in",
                "ar",
                "ll",
                "an",
                "er",
                "st",
                "or",
                "en",
                "on",
                "gh",
                "ro",
                "le",
                "ck",
                "la",
                "ur",
                "un",
                "el",
                "th",
                "il",
                "li",
                "re",
                "al",
                "ne",
                "ri",
                "ra",
                "ma",
                "ua",
                "be",
                "us",
                "ch",
                "ea",
                "av",
                "oo",
                "mi",
                "oy",
                "au",
                "ir",
                "sa",
                "no",
                "ru",
                "yn",
                "at",
                "gm",
                "nb",
                "xx",
                "ah",
                "wa",
            ]
        if count == 3:
            return [
                "lin",
                "coc",
                "all",
                "kil",
                "own",
                "agh",
                "ath",
                "ree",
                "roa",
                "ill",
                "ick",
                "ore",
                "ort",
                "ast",
                "for",
                "arr",
                "ane",
                "clo",
                "err",
                "gal",
                "ros",
                "col",
                "een",
                "ock",
                "ard",
                "and",
                "ark",
                "coo",
                "est",
                "ugh",
                "ant",
                "era",
                "ter",
                "dun",
                "lea",
                "ull",
                "gla",
                "oun",
                "lis",
                "han",
                "mon",
                "igo",
                "roo",
                "her",
                "iel",
                "ack",
                "car",
                "rin",
                "len",
                "cor",
                "cla",
                "nch",
                "fer",
                "the",
                "ran",
                "our",
                "hur",
                "kin",
                "gan",
                "urr",
                "bea",
                "aun",
                "dro",
                "bel",
                "ton",
                "boy",
                "ana",
                "urg",
                "nna",
                "ove",
                "ans",
                "owe",
                "ale",
                "den",
                "nis",
                "rea",
                "bbe",
                "sey",
                "eel",
                "oll",
                "doo",
                "ile",
                "eal",
                "ain",
                "ann",
                "cre",
                "ebr",
                "uck",
                "arn",
                "air",
                "lei",
                "eme",
                "ash",
                "aig",
                "roe",
                "rum",
                "hin",
                "awn",
                "aul",
                "fin",
                "tem",
                "ava",
                "beg",
                "ake",
                "tra",
                "com",
                "rah",
                "ert",
                "ske",
                "can",
                "der",
                "ron",
                "ave",
                "pat",
                "ous",
                "noc",
                "ola",
                "spi",
                "ell",
                "ini",
                "cam",
                "int",
                "mar",
                "moy",
                "ott",
                "mim",
                "coi",
                "inn",
                "mur",
                "bri",
                "axo",
                "lip",
                "ead",
                "ema",
                "uam",
                "uff",
                "bun",
                "ara",
                "esa",
                "irc",
                "ach",
                "lyr",
                "art",
                "rie",
                "ona",
                "cur",
                "lug",
                "ace",
                "qua",
                "ham",
                "alp",
                "oti",
                "too",
                "oge",
                "rus",
                "ite",
                "ole",
                "bra",
                "lia",
                "bro",
                "lyn",
                "goo",
                "anm",
                "urb",
                "uth",
                "gin",
                "ean",
                "mer",
                "oor",
                "dri",
                "gow",
                "sor",
                "mir",
                "fah",
                "tus",
                "hee",
                "rne",
                "enu",
                "leb",
                "lat",
                "pea",
                "tri",
                "aty",
                "wee",
                "ith",
                "aum",
                "ank",
                "tom",
                "roy",
                "har",
                "nee",
                "con",
                "hru",
                "lao",
                "tim",
                "sto",
                "rlo",
                "arl",
                "inr",
                "sli",
                "hil",
                "nra",
                "tho",
                "nit",
                "lke",
                "val",
                "rec",
                "gil",
                "dow",
                "eig",
                "pal",
                "igd",
                "ssa",
                "dof",
                "tti",
                "wli",
                "kst",
                "nod",
                "orn",
                "amh",
                "abh",
                "spr",
                "rdm",
                "fwa",
                "maa",
                "xxx",
            ]

    addr_sets = [
        set([i for i in ngrams(a, count) if len(i) >= count]) for a in addresses
    ]

    covers = defaultdict(set)
    for i, s in enumerate(addr_sets):
        for bg in s:
            covers[bg].add(i)

    uncovered = set(range(len(addresses)))
    chosen = []

    while uncovered:
        best = max(covers, key=lambda bg: len(covers[bg] & uncovered))

        covered = covers[best] & uncovered
        if not covered:
            break

        chosen.append(best)
        uncovered -= covered

    return chosen


def parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%a, %d %b %Y %H:%M:%S GMT").date()


def normalise(properties, field_map, date_fields=None):
    date_fields = date_fields or set()
    out = {}
    for old, new in field_map.items():
        value = properties.get(old)
        if new in date_fields:
            value = parse_date(value)
        out[new] = value
    return out


SEARCH_MAX_FIELD_LENGTH = 50


def _planning_databases(counties=None):
    return (
        (name, entry.database, entry.model)
        for name, entry in REGISTRY.items()
        if counties is None or name in counties
    )


def _ensure_search_schema(database, model):
    """Add model columns missing from databases created by older releases."""
    table = model._meta.table_name
    existing = {column.name for column in database.db.get_columns(table)}
    missing = [
        field for field in model._meta.sorted_fields if field.name not in existing
    ]
    if not missing:
        return

    migrator = SqliteMigrator(database.db)
    operations = []
    for field in missing:
        compatible_field = field.clone()
        compatible_field.null = True
        operations.append(migrator.add_column(table, field.name, compatible_field))
    migrate(*operations)


def _search_terms(values):
    if not values:
        return []
    if isinstance(values, str):
        values = values.split(",")
    return [clean_address_for_comparison(value) for value in values if value]


def _search_value(value, truncate):
    if value is None:
        return ""
    value = str(value)
    if truncate and len(value) > SEARCH_MAX_FIELD_LENGTH:
        return f"{value[:SEARCH_MAX_FIELD_LENGTH]}..."
    return value


def _first_search_value(result, model_fields):
    for model_field in model_fields:
        value = getattr(result, model_field, None)
        if value is not None:
            return value
    return None


def _search_row(source, result, include_all_features, truncate):
    from planning_permission.schema import normalise_record

    if include_all_features:
        row = {"source": source}
        for field in result._meta.sorted_fields:
            row[field.name] = _search_value(getattr(result, field.name), truncate)
        return row
    return {
        "source": source,
        **{
            key: _search_value(value, truncate)
            for key, value in normalise_record(result).items()
        },
    }


def search(
    address_substrs=None,
    exclude_address_substrs=None,
    counties=None,
    include_all_features=False,
    truncate=False,
    databases=None,
    reference=None,
    received_from=None,
    received_to=None,
    decision=None,
    status=None,
):
    from planning_permission.schema import normalise_record
    from planning_permission.refresh import read_metadata

    if received_from and received_to and received_from > received_to:
        raise ValueError("received_from must not be after received_to")
    included = _search_terms(address_substrs)
    excluded = _search_terms(exclude_address_substrs)
    if isinstance(counties, str):
        counties = [counties]
    selected_counties = {county.casefold() for county in counties} if counties else None
    databases = (
        _planning_databases(selected_counties) if databases is None else databases
    )

    rows = []
    for database_config in databases:
        source, database, *models = database_config
        if selected_counties is not None and source.casefold() not in selected_counties:
            continue
        if models:
            _ensure_search_schema(database, models[0])
        metadata = read_metadata(database.db) if hasattr(database, "db") else {}
        for result in database.filter(
            address_substrs=included,
            exclude_address_substrs=excluded,
            partial=True,
        ):
            canonical = normalise_record(result)
            if (
                reference
                and str(canonical["application_number"] or "").casefold()
                != reference.casefold()
            ):
                continue
            if (
                decision
                and decision.casefold()
                not in str(canonical["decision"] or "").casefold()
            ):
                continue
            if (
                status
                and status.casefold() not in str(canonical["status"] or "").casefold()
            ):
                continue
            received = canonical["received"]
            if received_from and (not received or received < received_from):
                continue
            if received_to and (not received or received > received_to):
                continue
            row = _search_row(source, result, include_all_features, truncate)
            row["last_updated"] = metadata.get("last_success", "unknown")
            rows.append(row)
    return rows


@backoff.on_exception(
    backoff.expo, (requests.exceptions.RequestException,), max_tries=5
)
def get(url, headers=None, session=None):
    sleep(SLEEP_BETWEEN_REQUESTS)
    client = session or requests
    response = client.get(url, headers=headers, timeout=60)
    if response.status_code == 404:
        return response
    else:
        response.raise_for_status()
    return response


@backoff.on_exception(
    backoff.expo, (requests.exceptions.RequestException,), max_tries=5
)
def post(url, data, headers=None, session=None):
    sleep(SLEEP_BETWEEN_REQUESTS)
    client = session or requests
    response = client.post(url, data=data, headers=headers, timeout=60)
    response.raise_for_status()
    return response


def validate_download(records, expected, source):
    if len(records) != expected:
        raise ValueError(
            f"Incomplete download from {source}: expected {expected}, got {len(records)}"
        )
    # Validate page identity where the source supplies stable feature IDs.
    ids = []
    for record in records:
        identity = next(
            (
                (key, record[key])
                for key in ("OBJECTID", "OBJECTID_1", "FID")
                if record.get(key) is not None
            ),
            None,
        )
        if identity is None:
            ids = []
            break
        ids.append(identity)
    if len(set(ids)) != len(ids):
        raise ValueError(f"Duplicate feature IDs in download from {source}")
    from planning_permission.telemetry import record_fetch

    record_fetch(len(records))


def arcgis_get_count(url, session, where="1=1"):
    count_response = session.get(
        url,
        params={"f": "json", "where": where, "returnCountOnly": "true"},
        timeout=120,
    )
    count_response.raise_for_status()
    return count_response.json()["count"]


def arcgis_get_results(
    url,
    session,
    total,
    batch_size=2000,
    skip_sort=False,
    where="1=1",
    prefix="",
):
    bar = progressbar.ProgressBar(max_value=total, prefix=prefix)
    bar.start()
    records = []
    offset = 0
    while offset < total:
        response = session.get(
            url,
            params={
                "f": "json",
                "where": where,
                "outFields": "*",
                "returnGeometry": "false",
                "resultOffset": offset,
                "resultRecordCount": batch_size,
                "orderByFields": "OBJECTID_1 ASC" if not skip_sort else "",
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            raise RuntimeError(payload["error"])
        page = [feature["attributes"] for feature in payload.get("features", [])]
        if not page:
            break
        records.extend(page)
        offset += len(page)
        bar.update(min(offset, total))
        if payload.get("exceededTransferLimit") is False:
            break
        sleep(SLEEP_BETWEEN_REQUESTS)
    bar.finish()
    validate_download(records, total, url)
    return records


def calc_batches(objects):
    return math.ceil(len(objects) / INSERT_BATCH_SIZE)


def write_to_db(db, obj, objects):
    from planning_permission.refresh import replace_dataset

    return replace_dataset(db.db, obj, objects, INSERT_BATCH_SIZE)


def arcgis_download(URL, skip_sort=False, where="1=1", prefix=""):
    session = requests.Session()
    total = arcgis_get_count(URL, session, where=where)
    return arcgis_get_results(
        URL, session, total, skip_sort=skip_sort, where=where, prefix=prefix
    )
