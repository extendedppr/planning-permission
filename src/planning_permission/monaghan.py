from planning_permission.local_register import create_local_download
from planning_permission.settings import MONAGHAN_DB_LOCATION

MONAGHAN_URL = "https://services-eu1.arcgis.com/YDJmfAKmZVpOnK2Q/arcgis/rest/services/PlanningPoints/FeatureServer/0/query"
MonaghanObject, monaghan_db, download_monaghan = create_local_download(
    "monaghan",
    "Monaghan County Council",
    MONAGHAN_DB_LOCATION,
    (("register", MONAGHAN_URL),),
)
