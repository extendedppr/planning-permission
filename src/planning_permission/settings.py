import os

from planning_permission.registry import COUNTIES, REGISTRY

SLEEP_BETWEEN_REQUESTS = float(os.getenv("SLEEP_BETWEEN_REQUESTS", 1))


BASE_DATA_LOCATION = os.getenv(
    "PLANNING_PERMISSION_DATA_LOCATION", "/var/lib/planning_permission/"
)

INSERT_BATCH_SIZE = int(os.getenv("INSERT_BATCH_SIZE", 500))

PLANNING_PERMISSION_LOCATION = os.path.join(BASE_DATA_LOCATION, "geojson.json")
PLANNING_PERMISSION_DB_LOCATION = os.path.join(BASE_DATA_LOCATION, "db.sqlite")


# Keep adapter constants compatible while deriving paths from one county registry.
for county in COUNTIES:
    location = os.path.join(BASE_DATA_LOCATION, county)
    globals()[f"{county.upper()}_LOCATION"] = location
    globals()[f"{county.upper()}_DB_LOCATION"] = str(
        REGISTRY[county].database_path(BASE_DATA_LOCATION)
    )
    os.makedirs(location, exist_ok=True)

DUBLIN_SAVES_LOCATION = os.path.join(BASE_DATA_LOCATION, "dublin", "saves")
os.makedirs(DUBLIN_SAVES_LOCATION, exist_ok=True)
NATIONAL_REGISTER_COUNTIES = COUNTIES[15:]
NATIONAL_REGISTER_DB_LOCATIONS = {
    county: str(REGISTRY[county].database_path(BASE_DATA_LOCATION))
    for county in NATIONAL_REGISTER_COUNTIES
}
