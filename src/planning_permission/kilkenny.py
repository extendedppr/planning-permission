from planning_permission.local_register import create_local_download
from planning_permission.settings import KILKENNY_DB_LOCATION

KILKENNY_URL = "https://services-eu1.arcgis.com/ciqs2VrgJ6vG8Jqb/arcgis/rest/services/PlanningApplicationsKKpublic/FeatureServer/0/query"
KilkennyObject, kilkenny_db, download_kilkenny = create_local_download(
    "kilkenny",
    "Kilkenny County Council",
    KILKENNY_DB_LOCATION,
    (("register", KILKENNY_URL),),
)
