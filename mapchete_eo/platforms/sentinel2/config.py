from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional, Type, Union

from mapchete.path import MPathLike
from pydantic import BaseModel, ValidationError
from pydantic.functional_validators import BeforeValidator
from typing_extensions import Annotated

from mapchete_eo.archives.base import Archive
from mapchete_eo.base import BaseDriverConfig
from mapchete_eo.brdf.config import F_MODIS_PARAMS, BRDFModels
from mapchete_eo.io.path import ProductPathGenerationMethod
from mapchete_eo.known_catalogs import AWSSearchCatalogS2L2A, EarthSearchV1S2L2A
from mapchete_eo.platforms.sentinel2.path_mappers import (
    EarthSearchPathMapper,
    SinergisePathMapper,
)
from mapchete_eo.platforms.sentinel2.types import (
    CloudType,
    ProcessingLevel,
    ProductQIMaskResolution,
    Resolution,
    SceneClassification,
)
from mapchete_eo.search.config import StacSearchConfig
from mapchete_eo.types import TimeRange


def known_archive(v: Any, **args) -> Type[Archive]:
    if isinstance(v, str):
        return KnownArchives[v].value
    elif isinstance(v, type(Archive)):
        return v
    else:
        raise ValidationError(f"cannot validate {v} to archive")


ArchiveClsFromString = Annotated[Type[Archive], BeforeValidator(known_archive)]


class AWSL2ACOGv1(Archive):
    catalog_cls = EarthSearchV1S2L2A
    collection_name = "sentinel-2-l2a"
    processing_level = ProcessingLevel.level2a
    path_mapper_cls = EarthSearchPathMapper


class AWSL2AJP2(Archive):
    catalog_cls = AWSSearchCatalogS2L2A
    collection_name = "sentinel-s2-l2a"
    processing_level = ProcessingLevel.level2a
    path_mapper_cls = SinergisePathMapper


class KnownArchives(Enum):
    S2AWS_COG = AWSL2ACOGv1
    S2AWS_JP2 = AWSL2AJP2


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


class CacheConfig(BaseModel):
    path: MPathLike
    product_path_generation_method: ProductPathGenerationMethod = (
        ProductPathGenerationMethod.hash
    )
    intersection_percent: float = 100.0
    assets: List[str] = []
    assets_resolution: Resolution = Resolution.original
    keep: bool = False
    max_cloud_percent: float = 100.0
    max_disk_usage: float = 90.0
    brdf: Optional[BRDFConfig] = None
    zoom: int = 13


class Sentinel2DriverConfig(BaseDriverConfig):
    format: str = "Sentinel-2"
    time: Union[TimeRange, List[TimeRange]]
    archive: ArchiveClsFromString = AWSL2ACOGv1
    cat_baseurl: Optional[MPathLike] = None
    max_cloud_percent: int = 100
    footprint_buffer: float = -500
    stac_config: StacSearchConfig = StacSearchConfig()
    first_granule_only: bool = False
    utm_zone: Optional[int] = None
    with_scl: bool = False
    brdf: Optional[BRDFConfig] = None
    cache: Optional[CacheConfig] = None


class MaskConfig(BaseModel):
    # mask by footprint geometry
    footprint: bool = True
    # add pixel buffer to all masks
    buffer: int = 0
    # mask by L1C cloud types (either opaque, cirrus or all)
    l1c_cloud_type: Optional[CloudType] = None
    # mask using the snow/ice mask
    snow_ice: bool = False
    # mask using cloud probability classification
    cloud_probability_threshold: int = 100
    cloud_probability_resolution: ProductQIMaskResolution = ProductQIMaskResolution[
        "60m"
    ]
    # mask using cloud probability classification
    snow_probability_threshold: int = 100
    snow_probability_resolution: ProductQIMaskResolution = ProductQIMaskResolution[
        "60m"
    ]
    # mask using one or more of the SCL classes
    scl_classes: Optional[List[SceneClassification]] = None

    @staticmethod
    def parse(config: Union[dict, MaskConfig]) -> MaskConfig:
        """
        Make sure all values are parsed correctly
        """
        if isinstance(config, MaskConfig):
            return config

        elif isinstance(config, dict):
            # convert SCL classes to correct SceneClassification item
            scl_classes = config.get("scl_classes")
            if scl_classes:
                config["scl_classes"] = [
                    scene_cls
                    if isinstance(scene_cls, SceneClassification)
                    else SceneClassification[scene_cls]
                    for scene_cls in scl_classes
                ]

            return MaskConfig(**config)

        else:
            raise TypeError(
                f"mask configuration should either be a dictionary or a MaskConfig object, not {config}"
            )
