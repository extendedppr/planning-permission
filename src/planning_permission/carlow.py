from planning_permission.local_register import create_local_download
from planning_permission.settings import CARLOW_DB_LOCATION

CARLOW_URL = "https://services.arcgis.com/8zunLZWYXqzwJUYx/arcgis/rest/services/Planning_Applications/FeatureServer/0/query"
CarlowObject, carlow_db, download_carlow = create_local_download(
    "carlow", "Carlow County Council", CARLOW_DB_LOCATION, (("register", CARLOW_URL),)
)
