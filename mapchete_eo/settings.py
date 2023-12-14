from typing import Optional

from mapchete.path import MPath, MPathLike
from pydantic_settings import BaseSettings, SettingsConfigDict
from rasterio.crs import CRS


class Settings(BaseSettings):
    """
    Combine default settings with env variables.

    All settings can be set in the environment by adding the 'MHUB_' prefix
    and the settings in uppercase, e.g. MAPCHETE_EO_.
    """

    default_cache_location: MPathLike = MPath("s3://eox-mhub-cache/")
    default_catalog_crs: CRS = CRS.from_epsg(4326)
    blacklist: Optional[MPathLike] = None

    # read from environment
    model_config = SettingsConfigDict(env_prefix="MAPCHETE_EO_")


mapchete_eo_settings: Settings = Settings()
