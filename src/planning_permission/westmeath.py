from planning_permission.local_register import create_local_download
from planning_permission.settings import WESTMEATH_DB_LOCATION

WESTMEATH_URL = "https://services-eu1.arcgis.com/DsXSaNAVVnwb89Pt/arcgis/rest/services/Westmeath_Planning_Applications/FeatureServer/0/query"
WestmeathObject, westmeath_db, download_westmeath = create_local_download(
    "westmeath",
    "Westmeath County Council",
    WESTMEATH_DB_LOCATION,
    (("register", WESTMEATH_URL),),
)
