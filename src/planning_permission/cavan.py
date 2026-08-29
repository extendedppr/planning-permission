from planning_permission.local_register import create_local_download
from planning_permission.settings import CAVAN_DB_LOCATION

CAVAN_URL = "https://services-eu1.arcgis.com/JxeIFQJpAbht5VJy/arcgis/rest/services/Planning_Points/FeatureServer/0/query"
CavanObject, cavan_db, download_cavan = create_local_download(
    "cavan", "Cavan County Council", CAVAN_DB_LOCATION, (("register", CAVAN_URL),)
)
