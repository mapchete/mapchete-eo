from abc import ABC, abstractmethod

from mapchete.path import MPath

from mapchete_eo.platforms.sentinel2.processing_baseline import ProcessingBaseline
from mapchete_eo.platforms.sentinel2.types import (
    BandQI,
    L2ABand,
    ProductQI,
    ProductQIMaskResolution,
)


class S2PathMapper(ABC):
    """
    Abstract class to help mapping asset paths from metadata.xml to their
    locations of various data archives.

    This is mainly used for additional data like QI masks.
    """

    # All available bands for Sentinel-2 Level 2A.
    _bands = [band.name for band in L2ABand]

    processing_baseline: ProcessingBaseline

    @abstractmethod
    def product_qi_mask(
        self,
        qi_mask: ProductQI,
        resolution: ProductQIMaskResolution = ProductQIMaskResolution["60m"],
    ) -> MPath: ...

    @abstractmethod
    def classification_mask(self) -> MPath: ...

    @abstractmethod
    def cloud_probability_mask(
        self, resolution: ProductQIMaskResolution = ProductQIMaskResolution["60m"]
    ) -> MPath: ...

    @abstractmethod
    def snow_probability_mask(
        self, resolution: ProductQIMaskResolution = ProductQIMaskResolution["60m"]
    ) -> MPath: ...

    @abstractmethod
    def band_qi_mask(self, qi_mask: BandQI, band: L2ABand) -> MPath: ...

    @abstractmethod
    def technical_quality_mask(self, band: L2ABand) -> MPath: ...

    @abstractmethod
    def detector_footprints(self, band: L2ABand) -> MPath: ...

    def clear_cached_data(self) -> None: ...
