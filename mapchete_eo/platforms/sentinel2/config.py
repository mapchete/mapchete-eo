from __future__ import annotations

from typing import List, Optional, Union, Dict, Any, Callable

from mapchete.path import MPathLike
from pydantic import BaseModel, ValidationError, field_validator, model_validator

from mapchete_eo.base import BaseDriverConfig
from mapchete_eo.io.path import ProductPathGenerationMethod
from mapchete_eo.platforms.sentinel2.archives import ArchiveClsFromString, AWSL2ACOGv1
from mapchete_eo.platforms.sentinel2.brdf.config import BRDFModels
from mapchete_eo.platforms.sentinel2.customizations import (
    DataArchive,
    MetadataArchive,
    KNOWN_SOURCES,
)
from mapchete_eo.platforms.sentinel2.mapper_registry import MAPPER_REGISTRIES
from mapchete_eo.platforms.sentinel2.types import (
    CloudType,
    ProductQIMaskResolution,
    Resolution,
    SceneClassification,
)
from mapchete_eo.search.config import StacSearchConfig
from mapchete_eo.types import TimeRange


def known_catalog_to_url(stac_catalog: str) -> str:
    if stac_catalog in KNOWN_SOURCES:
        return KNOWN_SOURCES[stac_catalog]["stac_catalog"]
    return stac_catalog


class Source(BaseModel):
    """All information required to consume Sentinel-2 products."""

    stac_catalog: str

    # if known STAC catalog is given, fill in the defaults
    collections: Optional[List[str]] = None
    data_archive: Optional[DataArchive] = None
    metadata_archive: MetadataArchive = "roda"

    @model_validator(mode="before")
    def determine_data_source(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Handles short names of sources."""
        if isinstance(values, str):
            values = dict(stac_catalog=values)
        stac_catalog = values.get("stac_catalog")
        if stac_catalog in KNOWN_SOURCES:
            values.update(KNOWN_SOURCES[stac_catalog])
        else:
            # TODO: make sure catalog then is either a path or an URL
            pass
        return values

    @model_validator(mode="after")
    def verify_mappers(self) -> Source:
        # make sure all required mappers are registered
        self.get_id_mapper()
        self.get_asset_paths_mapper()
        self.get_s2metadata_mapper()
        return self

    def get_id_mapper(self) -> Callable:
        for key in MAPPER_REGISTRIES["ID"]:
            if self.stac_catalog == known_catalog_to_url(key):
                return MAPPER_REGISTRIES["ID"][key]
        else:
            raise ValueError(f"no ID mapper for {self.stac_catalog} found")

    def get_asset_paths_mapper(self) -> Union[Callable, None]:
        if self.data_archive is None:
            return None
        for key in MAPPER_REGISTRIES["asset paths"]:
            stac_catalog, data_archive = key
            if (
                self.stac_catalog == known_catalog_to_url(stac_catalog)
                and data_archive == self.data_archive
            ):
                return MAPPER_REGISTRIES["asset paths"][key]
        else:
            raise ValueError(
                f"no asset paths mapper from {self.stac_catalog} to {self.data_archive} found"
            )

    def get_s2metadata_mapper(self) -> Union[Callable, None]:
        if self.metadata_archive is None:
            return None
        for key in MAPPER_REGISTRIES["S2Metadata"]:
            stac_catalog, metadata_archive = key
            if (
                self.stac_catalog == known_catalog_to_url(stac_catalog)
                and metadata_archive == self.metadata_archive
            ):
                return MAPPER_REGISTRIES["S2Metadata"][key]
        else:
            raise ValueError(
                f"no S2Metadata mapper from {self.stac_catalog} to {self.metadata_archive} found"
            )


default_source = Source.model_validate(KNOWN_SOURCES["EarthSearch"])


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

    # new
    source: List[Source] = [default_source]

    # deprecated
    # for backwards compatibility, archive should be converted to
    # catalog & data_archive
    archive: ArchiveClsFromString = AWSL2ACOGv1

    # don't know yet how to handle this
    cat_baseurl: Optional[MPathLike] = None
    search_index: Optional[MPathLike] = None

    # custom params
    max_cloud_cover: float = 100.0
    stac_config: StacSearchConfig = StacSearchConfig()
    first_granule_only: bool = False
    utm_zone: Optional[int] = None
    with_scl: bool = False
    brdf: Optional[BRDFConfig] = None
    cache: Optional[CacheConfig] = None

    @model_validator(mode="before")
    def to_list(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Expands source to list."""
        for field in ["source"]:
            value = values.get(field)
            if value is not None and not isinstance(value, list):
                values[field] = [value]
        return values


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
