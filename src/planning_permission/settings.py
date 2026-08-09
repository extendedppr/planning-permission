import os
import sys

SLEEP_BETWEEN_REQUESTS = float(os.getenv("SLEEP_BETWEEN_REQUESTS", 1))


TEST_ENV = "pytest" in sys.modules or "unittest" in sys.modules


BASE_DATA_LOCATION = (
    os.getenv("PLANNING_PERMISSION_DATA_LOCATION", "/var/lib/planning_permission/")
    if not TEST_ENV
    else "/tmp/var/lib/planning_permission/"
)

PLANNING_PERMISSION_LOCATION = os.path.join(BASE_DATA_LOCATION, "geojson.json")
PLANNING_PERMISSION_DB_LOCATION = os.path.join(BASE_DATA_LOCATION, "db.sqlite")

DCC_LOCATION = os.path.join(BASE_DATA_LOCATION, "dcc")
DCC_SAVES_LOCATION = os.path.join(DCC_LOCATION, "saves")
DCC_DB_LOCATION = os.path.join(DCC_LOCATION, "db.sqlite")

CORK_LOCATION = os.path.join(BASE_DATA_LOCATION, "cork")
CORK_DB_LOCATION = os.path.join(CORK_LOCATION, "db.sqlite")

GALWAY_LOCATION = os.path.join(BASE_DATA_LOCATION, "galway")
GALWAY_DB_LOCATION = os.path.join(GALWAY_LOCATION, "db.sqlite")

KILDARE_LOCATION = os.path.join(BASE_DATA_LOCATION, "kildare")
KILDARE_DB_LOCATION = os.path.join(KILDARE_LOCATION, "db.sqlite")

os.makedirs(BASE_DATA_LOCATION, exist_ok=True)
os.makedirs(DCC_LOCATION, exist_ok=True)
os.makedirs(DCC_SAVES_LOCATION, exist_ok=True)
os.makedirs(CORK_LOCATION, exist_ok=True)
os.makedirs(GALWAY_LOCATION, exist_ok=True)
os.makedirs(KILDARE_LOCATION, exist_ok=True)
