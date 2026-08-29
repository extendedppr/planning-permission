import os
import sys

SLEEP_BETWEEN_REQUESTS = float(os.getenv("SLEEP_BETWEEN_REQUESTS", 1))


TEST_ENV = "pytest" in sys.modules or "unittest" in sys.modules


BASE_DATA_LOCATION = (
    os.getenv("PLANNING_PERMISSION_DATA_LOCATION", "/var/lib/planning_permission/")
    if not TEST_ENV
    else "/tmp/var/lib/planning_permission/"
)

INSERT_BATCH_SIZE = int(os.getenv("INSERT_BATCH_SIZE", 500))

PLANNING_PERMISSION_LOCATION = os.path.join(BASE_DATA_LOCATION, "geojson.json")
PLANNING_PERMISSION_DB_LOCATION = os.path.join(BASE_DATA_LOCATION, "db.sqlite")

DUBLIN_LOCATION = os.path.join(BASE_DATA_LOCATION, "dublin")
DUBLIN_SAVES_LOCATION = os.path.join(DUBLIN_LOCATION, "saves")
DUBLIN_DB_LOCATION = os.path.join(DUBLIN_LOCATION, "db.sqlite")

CORK_LOCATION = os.path.join(BASE_DATA_LOCATION, "cork")
CORK_DB_LOCATION = os.path.join(CORK_LOCATION, "db.sqlite")

GALWAY_LOCATION = os.path.join(BASE_DATA_LOCATION, "galway")
GALWAY_DB_LOCATION = os.path.join(GALWAY_LOCATION, "db.sqlite")

KILDARE_LOCATION = os.path.join(BASE_DATA_LOCATION, "kildare")
KILDARE_DB_LOCATION = os.path.join(KILDARE_LOCATION, "db.sqlite")

MEATH_LOCATION = os.path.join(BASE_DATA_LOCATION, "meath")
MEATH_DB_LOCATION = os.path.join(MEATH_LOCATION, "db.sqlite")

LIMERICK_LOCATION = os.path.join(BASE_DATA_LOCATION, "limerick")
LIMERICK_DB_LOCATION = os.path.join(LIMERICK_LOCATION, "db.sqlite")

TIPPERARY_LOCATION = os.path.join(BASE_DATA_LOCATION, "tipperary")
TIPPERARY_DB_LOCATION = os.path.join(TIPPERARY_LOCATION, "db.sqlite")

DONEGAL_LOCATION = os.path.join(BASE_DATA_LOCATION, "donegal")
DONEGAL_DB_LOCATION = os.path.join(DONEGAL_LOCATION, "db.sqlite")

WEXFORD_LOCATION = os.path.join(BASE_DATA_LOCATION, "wexford")
WEXFORD_DB_LOCATION = os.path.join(WEXFORD_LOCATION, "db.sqlite")

KERRY_LOCATION = os.path.join(BASE_DATA_LOCATION, "kerry")
KERRY_DB_LOCATION = os.path.join(KERRY_LOCATION, "db.sqlite")

WICKLOW_LOCATION = os.path.join(BASE_DATA_LOCATION, "wicklow")
WICKLOW_DB_LOCATION = os.path.join(WICKLOW_LOCATION, "db.sqlite")

LOUTH_LOCATION = os.path.join(BASE_DATA_LOCATION, "louth")
LOUTH_DB_LOCATION = os.path.join(LOUTH_LOCATION, "db.sqlite")

MAYO_LOCATION = os.path.join(BASE_DATA_LOCATION, "mayo")
MAYO_DB_LOCATION = os.path.join(MAYO_LOCATION, "db.sqlite")

CLARE_LOCATION = os.path.join(BASE_DATA_LOCATION, "clare")
CLARE_DB_LOCATION = os.path.join(CLARE_LOCATION, "db.sqlite")

WATERFORD_LOCATION = os.path.join(BASE_DATA_LOCATION, "waterford")
WATERFORD_DB_LOCATION = os.path.join(WATERFORD_LOCATION, "db.sqlite")

NATIONAL_REGISTER_COUNTIES = (
    "kilkenny",
    "westmeath",
    "laois",
    "offaly",
    "cavan",
    "roscommon",
    "sligo",
    "monaghan",
    "carlow",
    "longford",
    "leitrim",
)
NATIONAL_REGISTER_DB_LOCATIONS = {
    county: os.path.join(BASE_DATA_LOCATION, county, "db.sqlite")
    for county in NATIONAL_REGISTER_COUNTIES
}
KILKENNY_DB_LOCATION = NATIONAL_REGISTER_DB_LOCATIONS["kilkenny"]
WESTMEATH_DB_LOCATION = NATIONAL_REGISTER_DB_LOCATIONS["westmeath"]
LAOIS_DB_LOCATION = NATIONAL_REGISTER_DB_LOCATIONS["laois"]
OFFALY_DB_LOCATION = NATIONAL_REGISTER_DB_LOCATIONS["offaly"]
CAVAN_DB_LOCATION = NATIONAL_REGISTER_DB_LOCATIONS["cavan"]
ROSCOMMON_DB_LOCATION = NATIONAL_REGISTER_DB_LOCATIONS["roscommon"]
SLIGO_DB_LOCATION = NATIONAL_REGISTER_DB_LOCATIONS["sligo"]
MONAGHAN_DB_LOCATION = NATIONAL_REGISTER_DB_LOCATIONS["monaghan"]
CARLOW_DB_LOCATION = NATIONAL_REGISTER_DB_LOCATIONS["carlow"]
LONGFORD_DB_LOCATION = NATIONAL_REGISTER_DB_LOCATIONS["longford"]
LEITRIM_DB_LOCATION = NATIONAL_REGISTER_DB_LOCATIONS["leitrim"]

os.makedirs(BASE_DATA_LOCATION, exist_ok=True)
os.makedirs(DUBLIN_LOCATION, exist_ok=True)
os.makedirs(DUBLIN_SAVES_LOCATION, exist_ok=True)
os.makedirs(CORK_LOCATION, exist_ok=True)
os.makedirs(GALWAY_LOCATION, exist_ok=True)
os.makedirs(KILDARE_LOCATION, exist_ok=True)
os.makedirs(MEATH_LOCATION, exist_ok=True)
os.makedirs(LIMERICK_LOCATION, exist_ok=True)
os.makedirs(TIPPERARY_LOCATION, exist_ok=True)
os.makedirs(DONEGAL_LOCATION, exist_ok=True)
os.makedirs(WEXFORD_LOCATION, exist_ok=True)
os.makedirs(KERRY_LOCATION, exist_ok=True)
os.makedirs(WICKLOW_LOCATION, exist_ok=True)
os.makedirs(LOUTH_LOCATION, exist_ok=True)
os.makedirs(MAYO_LOCATION, exist_ok=True)
os.makedirs(CLARE_LOCATION, exist_ok=True)
os.makedirs(WATERFORD_LOCATION, exist_ok=True)
for location in NATIONAL_REGISTER_DB_LOCATIONS.values():
    os.makedirs(os.path.dirname(location), exist_ok=True)
