import os

from mapchete.path import MPath
from rasterio.crs import CRS

DEFAULT_CACHE_LOCATION: MPath = MPath(
    os.environ.get("MP_EO_DEFAULT_CACHE_LOCATION", "s3://eox-mhub-cache/")
)
DEFAULT_CATALOG_CRS: CRS = CRS.from_epsg(4326)
