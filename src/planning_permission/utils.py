import math
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
from peewee import chunked
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


SEARCH_DEFAULT_FIELDS = (
    ("application_number", ("application_number",)),
    ("status", ("application_status", "status")),
    ("type", ("application_type",)),
    ("decision", ("decision", "decision_code")),
    ("received", ("received_date", "registration_date")),
    ("decision_date", ("decision_date",)),
    ("description", ("development_description", "description")),
)

SEARCH_FIELDS_BY_SOURCE = {
    "dublin": (
        ("application_number", ("application_reference",)),
        ("status", ("status_description",)),
        ("type", ("application_type",)),
        ("decision", ("decision_text",)),
        ("received", ("received_date", "registration_date")),
        ("decision_date", ("decision_date",)),
        ("description", ("proposal",)),
    ),
}

SEARCH_MAX_FIELD_LENGTH = 50


def _planning_databases():
    """Load database instances lazily to avoid circular county imports."""
    from planning_permission.clare import ClareObject, clare_db
    from planning_permission.cork import CorkObject, cork_db
    from planning_permission.donegal import DonegalObject, donegal_db
    from planning_permission.dublin import DublinObject, dublin_db
    from planning_permission.galway import GalwayObject, galway_db
    from planning_permission.kerry import KerryObject, kerry_db
    from planning_permission.kildare import KildareObject, kildare_db
    from planning_permission.limerick import LimerickObject, limerick_db
    from planning_permission.louth import LouthObject, louth_db
    from planning_permission.mayo import MayoObject, mayo_db
    from planning_permission.meath import MeathObject, meath_db
    from planning_permission.tipperary import TipperaryObject, tipperary_db
    from planning_permission.waterford import WaterfordObject, waterford_db
    from planning_permission.wexford import WexfordObject, wexford_db
    from planning_permission.wicklow import WicklowObject, wicklow_db

    return (
        ("dublin", dublin_db, DublinObject),
        ("cork", cork_db, CorkObject),
        ("galway", galway_db, GalwayObject),
        ("kildare", kildare_db, KildareObject),
        ("meath", meath_db, MeathObject),
        ("limerick", limerick_db, LimerickObject),
        ("tipperary", tipperary_db, TipperaryObject),
        ("donegal", donegal_db, DonegalObject),
        ("wexford", wexford_db, WexfordObject),
        ("kerry", kerry_db, KerryObject),
        ("wicklow", wicklow_db, WicklowObject),
        ("louth", louth_db, LouthObject),
        ("mayo", mayo_db, MayoObject),
        ("clare", clare_db, ClareObject),
        ("waterford", waterford_db, WaterfordObject),
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
    if include_all_features:
        row = {"source": source}
        for field in result._meta.sorted_fields:
            row[field.name] = _search_value(getattr(result, field.name), truncate)
        return row

    row = {
        "source": source,
        "address": _search_value(getattr(result, "address", None), truncate),
    }
    fields = SEARCH_FIELDS_BY_SOURCE.get(source, SEARCH_DEFAULT_FIELDS)
    for output_field, model_fields in fields:
        row[output_field] = _search_value(
            _first_search_value(result, model_fields), truncate
        )
    return row


def search(
    address_substrs=None,
    exclude_address_substrs=None,
    *,
    include_all_features=False,
    truncate=False,
    databases=None,
):
    included = _search_terms(address_substrs)
    excluded = _search_terms(exclude_address_substrs)
    databases = _planning_databases() if databases is None else databases

    rows = []
    for database_config in databases:
        source, database, *models = database_config
        if models:
            _ensure_search_schema(database, models[0])
        for result in database.filter(
            address_substrs=included,
            exclude_address_substrs=excluded,
            partial=True,
        ):
            rows.append(_search_row(source, result, include_all_features, truncate))
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

    return records


def calc_batches(objects):
    return math.ceil(len(objects) / INSERT_BATCH_SIZE)


def write_to_db(db, obj, objects):
    print(f"About to insert {len(objects)} objects into the database")
    prefix = f"{obj.__name__.removesuffix('Object')}: "
    db.recreate()
    with db.db.atomic():
        for batch in progressbar.progressbar(
            chunked(objects, INSERT_BATCH_SIZE),
            max_value=calc_batches(objects),
            prefix=prefix,
        ):
            obj.bulk_create(batch, batch_size=INSERT_BATCH_SIZE)


def arcgis_download(URL, skip_sort=False, where="1=1", prefix=""):
    session = requests.Session()
    total = arcgis_get_count(URL, session, where=where)
    return arcgis_get_results(
        URL, session, total, skip_sort=skip_sort, where=where, prefix=prefix
    )
