from planning_permission.local_register import create_local_download
from planning_permission.settings import OFFALY_DB_LOCATION

OFFALY_URLS = (
    (
        "register",
        "https://services-eu1.arcgis.com/GoYdY5OITUvNLuuX/arcgis/rest/services/Historical_Planning_Applications/FeatureServer/0/query",
    ),
    (
        "historic",
        "https://services-eu1.arcgis.com/GoYdY5OITUvNLuuX/arcgis/rest/services/Historical_Planning_Applications/FeatureServer/3/query",
    ),
)
OffalyObject, offaly_db, download_offaly = create_local_download(
    "offaly", "Offaly County Council", OFFALY_DB_LOCATION, OFFALY_URLS
)
