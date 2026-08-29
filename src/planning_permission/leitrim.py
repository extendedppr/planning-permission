from planning_permission.local_register import create_local_download
from planning_permission.settings import LEITRIM_DB_LOCATION

LEITRIM_URL = "https://services7.arcgis.com/EhwGJvRfdoo8Udzk/arcgis/rest/services/AllPlanningApplications/FeatureServer/0/query"
LeitrimObject, leitrim_db, download_leitrim = create_local_download(
    "leitrim",
    "Leitrim County Council",
    LEITRIM_DB_LOCATION,
    (("register", LEITRIM_URL),),
)
