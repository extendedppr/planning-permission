from planning_permission.local_register import create_local_download
from planning_permission.settings import LAOIS_DB_LOCATION

LAOIS_URLS = (
    (
        "1978-1997",
        "https://services3.arcgis.com/Fhtysje9wqGrXAXb/arcgis/rest/services/Planning_applications_78_97/FeatureServer/0/query",
    ),
    (
        "pre-2010",
        "https://services3.arcgis.com/Fhtysje9wqGrXAXb/arcgis/rest/services/Planning_points_pre2010/FeatureServer/0/query",
    ),
    (
        "current",
        "https://utility.arcgis.com/usrsvcs/servers/f6717aa42d12440ca9fdd4909520efc8/rest/services/Planning_Sites_Laois/FeatureServer/0/query",
    ),
)
LaoisObject, laois_db, download_laois = create_local_download(
    "laois", "Laois County Council", LAOIS_DB_LOCATION, LAOIS_URLS
)
