from planning_permission.local_register import create_local_download
from planning_permission.settings import LONGFORD_DB_LOCATION

LONGFORD_URL = "https://services-eu1.arcgis.com/wbkaFF8VvpfZkfmC/arcgis/rest/services/Planning_Sites/FeatureServer/0/query"
LongfordObject, longford_db, download_longford = create_local_download(
    "longford",
    "Longford County Council",
    LONGFORD_DB_LOCATION,
    (("register", LONGFORD_URL),),
)
