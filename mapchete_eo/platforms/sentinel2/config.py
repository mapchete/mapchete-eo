from datetime import datetime
from mapchete.path import MPath
from pydantic import BaseModel
from typing import Union, List

from mapchete_eo.io.path import ProductPathGenerationMethod
from mapchete_eo.types import GeodataType
from mapchete_eo.search.config import StacSearchConfig
from mapchete_eo.platforms.sentinel2.types import Resolution, CloudType
from mapchete_eo.platforms.sentinel2.brdf import BRDFConfig


class CloudmaskConfig(BaseModel):
    format: GeodataType = GeodataType.vector
    raster_resolution: Resolution = Resolution["20m"]
    cloud_types: CloudType = CloudType.all


class CacheConfig(BaseModel, arbitrary_types_allowed=True):
    path: Union[str, MPath]
    product_path_generation_method: ProductPathGenerationMethod = (
        ProductPathGenerationMethod.hash
    )
    intersection_percent: float = 100.0
    cloudmasks: Union[CloudmaskConfig, None] = None
    assets: List[str] = []
    assets_resolution: Resolution = Resolution.original
    keep: bool = False
    max_cloud_percent: float = 100.0
    max_disk_usage: float = 90.0
    scl: bool = False
    qi_snw: bool = False
    qi_cld: bool = False
    aot: bool = False
    angles: list = []
    brdf: Union[BRDFConfig, None] = None
    zoom: int = 13
    check_cached_files_exist: bool = False
    cached_files_validation: bool = False


class DriverConfig(BaseModel, arbitrary_types_allowed=True):
    format: str = "Sentinel-2"
    start_time: Union[str, datetime]
    end_time: Union[str, datetime]
    cloudmasks: Union[CloudmaskConfig, None] = CloudmaskConfig()
    max_cloud_percent: int = 100
    footprint_buffer: float = -500
    stac_config: StacSearchConfig = StacSearchConfig()
    first_granule_only: bool = False
    utm_zone: Union[int, None] = None
    with_scl: bool = False
    brdf: Union[BRDFConfig, None] = None
    cache: Union[CacheConfig, None] = None
