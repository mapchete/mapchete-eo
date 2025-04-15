from __future__ import annotations

from typing import List, Optional, Union

from mapchete.path import MPathLike
from pydantic import (
    BaseModel,
    ValidationError,
    field_validator,
)

from mapchete_eo.base import BaseDriverConfig
from mapchete_eo.io.path import ProductPathGenerationMethod
from mapchete_eo.platforms.sentinel2.archives import ArchiveClsFromString, AWSL2ACOGv1
from mapchete_eo.platforms.sentinel2.brdf.config import BRDFModels
from mapchete_eo.platforms.sentinel2.types import (
    CloudType,
    ProductQIMaskResolution,
    Resolution,
    SceneClassification,
)
from mapchete_eo.search.config import StacSearchConfig
from mapchete_eo.types import TimeRange


class BRDFModelConfig(BaseModel):
    model: BRDFModels = BRDFModels.HLS
    bands: List[str] = ["blue", "green", "red", "nir"]
    resolution: Resolution = Resolution["60m"]
    footprints_cached_read: bool = False
    log10_bands_scale: bool = False
    per_detector_correction: bool = False

    # This correction value is applied to `fv` (kvol) and `fr` (kgeo) in the final steps of the BRDF param
    correction_weight: float = 1.0


class BRDFSCLClassConfig(BRDFModelConfig):
    scl_classes: List[SceneClassification]

    @field_validator("scl_classes", mode="before")
    @classmethod
    def to_scl_classes(cls, values: List[str]) -> List[SceneClassification]:
        out = []
        for value in values:
            if isinstance(value, SceneClassification):
                out.append(value)
            elif isinstance(value, str):
                out.append(SceneClassification[value])
            else:
                raise ValidationError("value must be mappable to SceneClassification")
        return out


class BRDFConfig(BRDFModelConfig):
    """
    Main BRDF configuration with optional sub-configurations for certain SCL classes.

    model: BRDF model
    bands: list of band names
    resolution: resolution BRDF is calculated on
    footprints_cached_read: download and read footprints from cache or not
    correction_weight: make correction stronger (>1) or weaker (<1)
    scl_specific_configurations: list of parameters like above plus SCL classes it
        should be applied to

    e.g.
    BRDFConfig(
        model="HLS",
        bands=["red", "green", "blue"],
        resolution="60m",
        footprints_cached_read=True,
        correction_weight=0.9,
        log10_bands_scale=True,
        scl_specific_configurations=[
            BRDFSCLClassConfig(
                scl_classes=["water"],
                model="HLS",
                bands=["red", "green", "blue"],
                resolution="60m",
                footprints_cached_read=True,
                correction_weight=1.3,
            )
        ]
    )

    """

    scl_specific_configurations: Optional[List[BRDFSCLClassConfig]] = None


class CacheConfig(BaseModel):
    path: MPathLike
    product_path_generation_method: ProductPathGenerationMethod = (
        ProductPathGenerationMethod.hash
    )
    intersection_percent: float = 100.0
    assets: List[str] = []
    assets_resolution: Resolution = Resolution.original
    keep: bool = False
    max_cloud_cover: float = 100.0
    max_disk_usage: float = 90.0
    brdf: Optional[BRDFConfig] = None
    zoom: int = 13


class Sentinel2DriverConfig(BaseDriverConfig):
    format: str = "Sentinel-2"
    time: Union[TimeRange, List[TimeRange]]
    archive: ArchiveClsFromString = AWSL2ACOGv1
    cat_baseurl: Optional[MPathLike] = None
    search_index: Optional[MPathLike] = None
    max_cloud_cover: float = 100.0
    stac_config: StacSearchConfig = StacSearchConfig()
    first_granule_only: bool = False
    utm_zone: Optional[int] = None
    with_scl: bool = False
    brdf: Optional[BRDFConfig] = None
    cache: Optional[CacheConfig] = None


class MaskConfig(BaseModel):
    # mask by footprint geometry
    footprint: bool = True
    # apply buffer (in meters!) to footprint
    footprint_buffer_m: float = -500
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
    # download masks before reading
    l1c_cloud_mask_cached_read: bool = False
    snow_ice_mask_cached_read: bool = False
    cloud_probability_cached_read: bool = False
    snow_probability_cached_read: bool = False
    scl_cached_read: bool = False

    @field_validator("scl_classes", mode="before")
    @classmethod
    def to_scl_classes(cls, values: List[str]) -> List[SceneClassification]:
        if values is None:
            return
        out = []
        for value in values:
            if isinstance(value, SceneClassification):
                out.append(value)
            elif isinstance(value, str):
                out.append(SceneClassification[value])
            else:
                raise ValidationError("value must be mappable to SceneClassification")
        return out

    @staticmethod
    def parse(config: Union[dict, MaskConfig]) -> MaskConfig:
        """
        Make sure all values are parsed correctly
        """
        if isinstance(config, MaskConfig):
            return config

        elif isinstance(config, dict):
            return MaskConfig(**config)

        else:
            raise TypeError(
                f"mask configuration should either be a dictionary or a MaskConfig object, not {config}"
            )
