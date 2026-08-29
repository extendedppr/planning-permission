from planning_permission.local_register import create_local_download
from planning_permission.settings import SLIGO_DB_LOCATION

SLIGO_URL = "https://services-eu1.arcgis.com/jgNFn6b1W4PAHceK/arcgis/rest/services/Public_Planning_Apps_View/FeatureServer/2/query"
SligoObject, sligo_db, download_sligo = create_local_download(
    "sligo", "Sligo County Council", SLIGO_DB_LOCATION, (("register", SLIGO_URL),)
)
