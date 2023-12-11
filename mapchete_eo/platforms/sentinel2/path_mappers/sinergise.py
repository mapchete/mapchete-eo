from mapchete.path import MPath, MPathLike

from mapchete_eo.platforms.sentinel2.path_mappers.base import S2PathMapper
from mapchete_eo.platforms.sentinel2.processing_baseline import ProcessingBaseline
from mapchete_eo.platforms.sentinel2.types import (
    BandQI,
    L2ABand,
    ProductQI,
    ProductQIMaskResolution,
)


class SinergisePathMapper(S2PathMapper):
    """
    Return true paths of product quality assets from the Sinergise S2 bucket.

    e.g.:
    B01 detector footprints: s3://sentinel-s2-l2a/tiles/51/K/XR/2020/7/31/0/qi/MSK_DETFOO_B01.gml
    Cloud masks: s3://sentinel-s2-l2a/tiles/51/K/XR/2020/7/31/0/qi/MSK_CLOUDS_B00.gml

    newer products however:
    B01 detector footprints: s3://sentinel-s2-l2a/tiles/51/K/XR/2022/6/6/0/qi/DETFOO_B01.jp2
    no vector cloudmasks available anymore
    """

    _PRE_0400_MASK_PATHS = {
        ProductQI.classification: "MSK_CLOUDS_B00.gml",
        ProductQI.cloud_probability: "CLD_{resolution}.jp2",  # are they really there?
        ProductQI.snow_probability: "SNW_{resolution}.jp2",  # are they really there?
        BandQI.detector_footprints: "MSK_DETFOO_{band_identifier}.gml",
        BandQI.technical_quality: "MSK_TECQUA_{band_identifier}.gml",
    }
    _POST_0400_MASK_PATHS = {
        ProductQI.classification: "CLASSI_B00.jp2",
        ProductQI.cloud_probability: "CLD_{resolution}.jp2",
        ProductQI.snow_probability: "SNW_{resolution}.jp2",
        BandQI.detector_footprints: "DETFOO_{band_identifier}.jp2",
        BandQI.technical_quality: "QUALIT_{band_identifier}.jp2",
    }

    def __init__(
        self,
        url: MPathLike,
        bucket: str = "sentinel-s2-l2a",
        protocol: str = "s3",
        baseline_version: str = "04.00",
        **kwargs,
    ):
        url = MPath.from_inp(url)
        tileinfo_path = url.parent / "tileInfo.json"
        self._path = MPath(
            "/".join(tileinfo_path.elements[-9:-1]), **tileinfo_path._kwargs
        )
        self._utm_zone, self._latitude_band, self._grid_square = self._path.split("/")[
            1:-4
        ]
        self._baseurl = bucket
        self._protocol = protocol
        self.processing_baseline = ProcessingBaseline.from_version(baseline_version)

    def product_qi_mask(
        self,
        qi_mask: ProductQI,
        resolution: ProductQIMaskResolution = ProductQIMaskResolution["60m"],
    ) -> MPath:
        """Determine product QI mask according to Sinergise bucket schema."""
        if self.processing_baseline.version < "04.00":
            mask_path = self._PRE_0400_MASK_PATHS[qi_mask]
        else:
            mask_path = self._POST_0400_MASK_PATHS[qi_mask]
        key = f"{self._path}/qi/{mask_path.format(resolution=resolution.name)}"
        return MPath.from_inp(f"{self._protocol}://{self._baseurl}/{key}")

    def classification_mask(self) -> MPath:
        return self.product_qi_mask(ProductQI.classification)

    def cloud_probability_mask(
        self, resolution: ProductQIMaskResolution = ProductQIMaskResolution["60m"]
    ) -> MPath:
        return self.product_qi_mask(ProductQI.cloud_probability, resolution=resolution)

    def snow_probability_mask(
        self, resolution: ProductQIMaskResolution = ProductQIMaskResolution["60m"]
    ) -> MPath:
        return self.product_qi_mask(ProductQI.snow_probability, resolution=resolution)

    def band_qi_mask(self, qi_mask: BandQI, band: L2ABand) -> MPath:
        """Determine product QI mask according to Sinergise bucket schema."""
        try:
            if self.processing_baseline.version < "04.00":
                mask_path = self._PRE_0400_MASK_PATHS[qi_mask]
            else:
                mask_path = self._POST_0400_MASK_PATHS[qi_mask]
        except KeyError:
            raise DeprecationWarning(
                f"'{qi_mask.name}' quality mask not found in this product"
            )
        key = f"{self._path}/qi/{mask_path.format(band_identifier=band.name)}"
        return MPath.from_inp(f"{self._protocol}://{self._baseurl}/{key}")

    def technical_quality_mask(self, band: L2ABand) -> MPath:
        return self.band_qi_mask(BandQI.technical_quality, band)

    def detector_footprints(self, band: L2ABand) -> MPath:
        return self.band_qi_mask(BandQI.detector_footprints, band)
