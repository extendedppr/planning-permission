from planning_permission.local_register import create_local_download
from planning_permission.settings import ROSCOMMON_DB_LOCATION

ROSCOMMON_URLS = (
    (
        "historical",
        "https://services1.arcgis.com/0g8o874l5un2eDgz/arcgis/rest/services/Planning_Finder_App_Planning_Points_Historical/FeatureServer/0/query",
    ),
    (
        "current",
        "https://services1.arcgis.com/0g8o874l5un2eDgz/arcgis/rest/services/Planning_Finder_App_Planning_Points/FeatureServer/0/query",
    ),
)
RoscommonObject, roscommon_db, download_roscommon = create_local_download(
    "roscommon", "Roscommon County Council", ROSCOMMON_DB_LOCATION, ROSCOMMON_URLS
)
