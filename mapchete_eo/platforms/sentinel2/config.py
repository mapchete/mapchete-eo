import datetime
from enum import Enum
from typing import List, Type, Union

from mapchete.path import MPath
from pydantic import BaseModel

from mapchete_eo.archives.base import Archive
from mapchete_eo.base import FormatParams
from mapchete_eo.brdf.config import F_MODIS_PARAMS, BRDFModels
from mapchete_eo.io.path import ProductPathGenerationMethod
from mapchete_eo.known_catalogs import EarthSearchV1S2L2A
from mapchete_eo.platforms.sentinel2.path_mappers import EarthSearchPathMapper
from mapchete_eo.platforms.sentinel2.types import CloudType, ProcessingLevel, Resolution
from mapchete_eo.search.config import StacSearchConfig
from mapchete_eo.types import GeodataType


class AWSL2ACOGv1(Archive):
    catalog_cls = EarthSearchV1S2L2A
    collection_name = "sentinel-2-l2a"
    processing_level = ProcessingLevel.level2a
    path_mapper_cls = EarthSearchPathMapper


class KnownArchives(Enum):
    S2AWS_COG = AWSL2ACOGv1


class BRDFConfig(BaseModel):
    model: BRDFModels = BRDFModels.HLS
    bands: List[str] = ["blue", "green", "red", "nir"]
    resolution: Resolution = Resolution["60m"]


class L2ABandFParams(Enum):
    B01 = F_MODIS_PARAMS[1]
    B02 = F_MODIS_PARAMS[2]
    B03 = F_MODIS_PARAMS[3]
    B04 = F_MODIS_PARAMS[4]
    B05 = F_MODIS_PARAMS[5]
    B06 = F_MODIS_PARAMS[6]
    B07 = F_MODIS_PARAMS[7]
    B08 = F_MODIS_PARAMS[8]
    B8A = F_MODIS_PARAMS[9]
    B09 = F_MODIS_PARAMS[10]
    B11 = F_MODIS_PARAMS[11]
    B12 = F_MODIS_PARAMS[12]


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


class DriverConfig(FormatParams, arbitrary_types_allowed=True):
    format: str = "Sentinel-2"
    start_time: Union[datetime.datetime, datetime.date]
    end_time: Union[datetime.datetime, datetime.date]
    archive: Type[Archive] = KnownArchives.S2AWS_COG.value
    cat_baseurl: Union[str, None] = None
    cloudmasks: Union[CloudmaskConfig, None] = CloudmaskConfig()
    max_cloud_percent: int = 100
    footprint_buffer: float = -500
    stac_config: StacSearchConfig = StacSearchConfig()
    first_granule_only: bool = False
    utm_zone: Union[int, None] = None
    with_scl: bool = False
    brdf: Union[BRDFConfig, None] = None
    cache: Union[CacheConfig, None] = None
