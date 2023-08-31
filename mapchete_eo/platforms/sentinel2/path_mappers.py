"""
A path mapper maps from an metadata XML file to additional metadata
on a given archive or a local SAFE file.
"""
import json
import logging
import xml.etree.ElementTree as etree
from abc import ABC, abstractmethod
from enum import Enum
from functools import cached_property
from typing import Union

from mapchete.path import MPath

from mapchete_eo.io import open_xml
from mapchete_eo.platforms.sentinel2.processing_baseline import ProcessingBaseline
from mapchete_eo.platforms.sentinel2.types import BandQIMask, L2ABand, ProductQIMask

logger = logging.getLogger(__name__)


# available product mask resolutions
ProductMaskResolution = Enum(
    "ProductMaskResolution",
    {
        "20m": 20,
        "60m": 60,
    },
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
        qi_mask: ProductQIMask,
        resolution: ProductMaskResolution = ProductMaskResolution["60m"],
    ) -> MPath:
        ...

    @abstractmethod
    def classification_mask(self) -> MPath:
        ...

    @abstractmethod
    def cloud_probability_mask(
        self, resolution: ProductMaskResolution = ProductMaskResolution["60m"]
    ) -> MPath:
        ...

    @abstractmethod
    def snow_probability_mask(
        self, resolution: ProductMaskResolution = ProductMaskResolution["60m"]
    ) -> MPath:
        ...

    @abstractmethod
    def band_qi_mask(self, qi_mask: BandQIMask, band: L2ABand) -> MPath:
        ...

    @abstractmethod
    def technical_quality_mask(self, band: L2ABand) -> MPath:
        ...

    @abstractmethod
    def detector_footprints(self, band: L2ABand) -> MPath:
        ...


class XMLMapper(S2PathMapper):
    def __init__(
        self, metadata_xml: MPath, xml_root: Union[etree.Element, None] = None, **kwargs
    ):
        self.metadata_xml = metadata_xml
        self._cached_xml_root = xml_root
        self._metadata_dir = metadata_xml.parent

    @cached_property
    def xml_root(self):
        if self._cached_xml_root is None:
            self._cached_xml_root = open_xml(self.metadata_xml)
        return self._cached_xml_root

    @cached_property
    def processing_baseline(self):
        # try to guess processing baseline from product id
        def _get_version(tag="TILE_ID"):
            product_id = next(self.xml_root.iter(tag)).text
            appendix = product_id.split("_")[-1]
            if appendix.startswith("N"):
                return appendix.lstrip("N")

        version = _get_version()
        try:
            return ProcessingBaseline.from_version(version)
        except Exception:
            # try use L1C product version as fallback
            try:
                l1c_version = _get_version("L1C_TILE_ID")
            except StopIteration:
                l1c_version = "02.06"
            if l1c_version is not None:
                return ProcessingBaseline.from_version(f"{l1c_version}")

    def product_qi_mask(
        self,
        qi_mask: ProductQIMask,
        resolution: ProductMaskResolution = ProductMaskResolution["60m"],
    ) -> MPath:
        """Determine product QI mask from metadata.xml."""
        qi_mask_type = dict(self.processing_baseline.product_mask_types)[qi_mask]
        for i in self.xml_root.iter():
            if i.tag == "MASK_FILENAME" and i.get("type") == qi_mask_type:
                return self._metadata_dir / i.text
        else:
            raise KeyError(f"no {qi_mask_type} item found in metadata")

    def classification_mask(self) -> MPath:
        return self.product_qi_mask(ProductQIMask.classification)

    def cloud_probability_mask(
        self, resolution: ProductMaskResolution = ProductMaskResolution["60m"]
    ) -> MPath:
        # TODO: handle resolution
        return self.product_qi_mask(ProductQIMask.cloud_probability)

    def snow_probability_mask(
        self, resolution: ProductMaskResolution = ProductMaskResolution["60m"]
    ) -> MPath:
        # TODO: handle resolution
        return self.product_qi_mask(ProductQIMask.snow_probability)

    def band_qi_mask(self, qi_mask: BandQIMask, band: L2ABand) -> MPath:
        """Determine band QI mask from metadata.xml."""
        if qi_mask.name not in dict(self.processing_baseline.band_mask_types).keys():
            raise DeprecationWarning(
                f"QI mask '{qi_mask}' not available for this product"
            )
        mask_types = set()
        for masks in self.xml_root.iter("Pixel_Level_QI"):
            if masks.get("geometry") == "FULL_RESOLUTION":
                for mask_path in masks:
                    qi_mask_type = dict(self.processing_baseline.band_mask_types)[
                        qi_mask
                    ]
                    mask_type = mask_path.get("type")
                    mask_types.add(mask_type)
                    if mask_type == qi_mask_type and mask_path.get("bandId"):
                        band_idx = int(mask_path.get("bandId"))
                        if band_idx == band.value:
                            return self._metadata_dir / mask_path.text
                else:
                    raise KeyError(
                        f"no {qi_mask_type} for band {band.name} not found in metadata: {', '.join(mask_types)}"
                    )
        else:
            raise KeyError(
                f"no {qi_mask_type} not found in metadata: {', '.join(mask_types)}"
            )

    def technical_quality_mask(self, band: L2ABand) -> MPath:
        return self.band_qi_mask(BandQIMask.technical_quality, band)

    def detector_footprints(self, band: L2ABand) -> MPath:
        return self.band_qi_mask(BandQIMask.detector_footprints, band)


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
        ProductQIMask.classification: "MSK_CLOUDS_B00.gml",
        ProductQIMask.cloud_probability: "CLD_20m.jp2",  # are they really there?
        ProductQIMask.snow_probability: "SNW_20m.jp2",  # are they really there?
        BandQIMask.detector_footprints: "MSK_DETFOO_{band_identifier}.gml",
        BandQIMask.technical_quality: "MSK_TECQUA_{band_identifier}.gml",
    }
    _POST_0400_MASK_PATHS = {
        ProductQIMask.classification: "CLASSI_B00.jp2",
        ProductQIMask.cloud_probability: "CLD_20m.jp2",
        ProductQIMask.snow_probability: "SNW_20m.jp2",
        BandQIMask.detector_footprints: "DETFOO_{band_identifier}.jp2",
        BandQIMask.technical_quality: "QUALIT_{band_identifier}.jp2",
    }

    def __init__(
        self,
        url: Union[MPath, str],
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
        qi_mask: ProductQIMask,
        resolution: ProductMaskResolution = ProductMaskResolution["60m"],
    ) -> MPath:
        """Determine product QI mask according to Sinergise bucket schema."""
        if self.processing_baseline.version < "04.00":
            mask_path = self._PRE_0400_MASK_PATHS[qi_mask]
        else:
            mask_path = self._POST_0400_MASK_PATHS[qi_mask]
        key = f"{self._path}/qi/{mask_path}"
        return MPath.from_inp(f"{self._protocol}://{self._baseurl}/{key}")

    def classification_mask(self) -> MPath:
        return self.product_qi_mask(ProductQIMask.classification)

    def cloud_probability_mask(
        self, resolution: ProductMaskResolution = ProductMaskResolution["60m"]
    ) -> MPath:
        return self.product_qi_mask(ProductQIMask.cloud_probability)

    def snow_probability_mask(
        self, resolution: ProductMaskResolution = ProductMaskResolution["60m"]
    ) -> MPath:
        return self.product_qi_mask(ProductQIMask.snow_probability)

    def band_qi_mask(self, qi_mask: BandQIMask, band: L2ABand) -> MPath:
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
        return self.band_qi_mask(BandQIMask.technical_quality, band)

    def detector_footprints(self, band: L2ABand) -> MPath:
        return self.band_qi_mask(BandQIMask.detector_footprints, band)


class EarthSearchPathMapper(SinergisePathMapper):
    """
    The COG archive maintained by E84 and covered by EarthSearch does not hold additional data
    such as the GML files. This class maps the metadata masks to the current EarthSearch product.

    e.g.:
    B01 detector footprints: s3://sentinel-s2-l2a/tiles/51/K/XR/2020/7/31/0/qi/MSK_DETFOO_B01.gml
    Cloud masks: s3://sentinel-s2-l2a/tiles/51/K/XR/2020/7/31/0/qi/MSK_CLOUDS_B00.gml

    newer products however:
    B01 detector footprints: s3://sentinel-s2-l2a/tiles/51/K/XR/2022/6/6/0/qi/DETFOO_B01.jp2
    no vector cloudmasks available anymore
    """

    def __init__(
        self,
        metadata_xml: MPath,
        alternative_metadata_baseurl: str = "sentinel-s2-l2a",
        protocol: str = "s3",
        baseline_version: str = "04.00",
        **kwargs,
    ):
        basedir = metadata_xml.parent
        tileinfo = json.loads((basedir / "tileinfo_metadata.json").read_text())
        self._path = MPath.from_inp(tileinfo["path"])
        self._utm_zone, self._latitude_band, self._grid_square = basedir.elements[-6:-3]
        self._baseurl = alternative_metadata_baseurl
        self._protocol = protocol
        self.processing_baseline = ProcessingBaseline.from_version(baseline_version)


def s2path_mapper_guesser(
    url: str,
    **kwargs,
):
    """Guess S2PathMapper based on URL.

    If a new path mapper is added in this module, it should also be added to this function
    in order to be detected.
    """
    if url.startswith(
        ("https://roda.sentinel-hub.com/sentinel-s2-l2a/", "s3://sentinel-s2-l2a/")
    ) or url.startswith(
        ("https://roda.sentinel-hub.com/sentinel-s2-l1c/", "s3://sentinel-s2-l1c/")
    ):
        return SinergisePathMapper(url, **kwargs)
    elif url.startswith(
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/"
    ):
        return EarthSearchPathMapper(url, **kwargs)
    else:
        return XMLMapper(url, **kwargs)
