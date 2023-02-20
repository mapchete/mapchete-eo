from abc import ABC, abstractmethod
from cached_property import cached_property
from fsspec.exceptions import FSTimeoutError
import json
import logging
from mapchete.io import fs_from_path
import os
from retry import retry
from typing import Union
import xml.etree.ElementTree as etree

from mapchete_eo.platforms.sentinel2.processing_baseline import ProcessingBaseline
from mapchete_eo.settings import MP_EO_IO_RETRY_SETTINGS

logger = logging.getLogger(__name__)


QI_MASKS = {
    # Finer cloud mask
    # ----------------
    # A finer cloud mask is computed on final Level-1C images. It is provided in the final
    # reference frame (ground geometry).
    "clouds": "MSK_CLOUDS",
    #
    # Radiometric quality masks
    # -------------------------
    # A defective pixels’ mask, containing the position of defective pixels.
    "defective": "MSK_DEFECT",
    #
    # A saturated pixels’ mask, containing the position of the saturated pixels in the
    # full resolution image.
    "saturated": "MSK_SATURA",
    #
    # A nodata pixels’ mask, containing the position of pixels with no data.
    "nodata": "MSK_NODATA",
    #
    # Detector footprint mask
    # -----------------------
    # A mask providing the ground footprint of each detector within a Tile.
    "detector_footprints": "MSK_DETFOO",
    #
    # Technical quality mask files
    # ----------------------------
    # These vector files contain a list of polygons in Level-1A reference frame indicating
    # degraded quality areas in the image.
    "technical_quality": "MSK_TECQUA",
}


@retry(
    logger=logger,
    exceptions=(TimeoutError, FSTimeoutError),
    **MP_EO_IO_RETRY_SETTINGS,
)
def open_metadata_xml(metadata_xml):
    logger.debug(f"open {metadata_xml}")
    with fs_from_path(metadata_xml).open(metadata_xml, "r") as metadata:
        return etree.fromstring(metadata.read())


class S2PathMapper(ABC):
    """
    Abstract class to help mapping asset paths from metadata.xml to their
    locations of various data archives.
    """

    # All available bands for Sentinel-2 Level 1C.
    _bands = [
        "B01",
        "B02",
        "B03",
        "B04",
        "B05",
        "B06",
        "B07",
        "B08",
        "B8A",
        "B09",
        "B10",
        "B11",
        "B12",
    ]

    processing_baseline: ProcessingBaseline

    @staticmethod
    def from_xml_url(url, **kwargs) -> "S2PathMapper":
        if url.startswith(
            ("https://roda.sentinel-hub.com/sentinel-s2-l2a/", "s3://sentinel-s2-l2a/")
        ) or url.startswith(
            ("https://roda.sentinel-hub.com/sentinel-s2-l1c/", "s3://sentinel-s2-l1c/")
        ):
            # TODO maybe add more checks for invalid input URLs
            return SinergisePathMapper(
                tileinfo_path=f"{os.path.dirname(url)}/tileInfo.json", **kwargs
            )
        elif url.startswith(
            "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/"
        ):
            return EarthSearchPathMapper(url, **kwargs)
        else:
            return XMLMapper(url, **kwargs)

    def band_name_to_id(self, band_name) -> int:
        for id, band in enumerate(self._bands):
            if band_name == band:
                return id
        else:
            raise KeyError(f"band name {band_name} not found in {self._bands}")

    @abstractmethod
    def cloud_mask(self) -> str:
        ...

    @abstractmethod
    def band_qi_mask(
        self, qi_mask: Union[str, None] = None, band=Union[str, int, None]
    ) -> str:
        ...


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
        "clouds": "MSK_CLOUDS_B00.gml",
        "defective": "MSK_DEFECT_{band}.gml",
        "saturated": "MSK_SATURA_{band}.gml",
        "nodata": "MSK_NODATA_{band}.gml",
        "detector_footprints": "MSK_DETFOO_{band}.gml",
        "technical_quality": "MSK_TECQUA_{band}.gml",
    }
    _POST_0400_MASK_PATHS = {
        "clouds": "CLASSI_B00.jp2",
        "detector_footprints": "DETFOO_{band}.jp2",
        "technical_quality": "QUALIT_{band}.jp2",
    }

    def __init__(
        self,
        tileinfo_path: str,
        bucket="sentinel-s2-l2a",
        protocol="s3",
        baseline_version="04.00",
        **kwargs,
    ):
        self._path = "/".join(tileinfo_path.split("/")[-9:-1])
        self._utm_zone, self._latitude_band, self._grid_square = self._path.split("/")[
            1:-4
        ]
        self._baseurl = bucket
        self._protocol = protocol
        self.processing_baseline = ProcessingBaseline.from_version(baseline_version)

    def cloud_mask(self) -> str:
        if self.processing_baseline.version < "04.00":
            mask_path = self._PRE_0400_MASK_PATHS["clouds"]
        else:
            mask_path = self._POST_0400_MASK_PATHS["clouds"]
        key = f"{self._path}/qi/{mask_path}"
        return f"{self._protocol}://{self._baseurl}/{key}"

    def _band_mask(self, qi_mask, band=None) -> str:
        try:
            if self.processing_baseline.version < "04.00":
                mask_path = self._PRE_0400_MASK_PATHS[qi_mask]
            else:
                mask_path = self._POST_0400_MASK_PATHS[qi_mask]
        except KeyError:
            raise DeprecationWarning(
                f"'{qi_mask}' quality mask not found in this product"
            )
        if band not in self._bands:
            raise KeyError(f"band must be one of {self._bands}, not {band}")
        key = f"{self._path}/qi/{mask_path.format(band=band)}"
        return f"{self._protocol}://{self._baseurl}/{key}"

    def band_qi_mask(self, qi_mask=None, band=None) -> str:
        return self._band_mask(qi_mask=qi_mask, band=band)


class XMLMapper(S2PathMapper):
    _cached_xml_root = None

    def __init__(
        self, metadata_xml: str, xml_root: Union[etree.Element, None] = None, **kwargs
    ):
        self._cached_xml_root = xml_root
        self._metadata_dir = os.path.dirname(metadata_xml)

    @cached_property
    def xml_root(self):
        if self._cached_xml_root is None:
            self._cached_xml_root = open_metadata_xml(self.metadata_xml)
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

    def _qi_mask_abs_path(self, qi_path) -> str:
        return os.path.join(self._metadata_dir, qi_path)

    def cloud_mask(self) -> str:
        for i in self.xml_root.iter():
            if i.tag == "MASK_FILENAME" and i.get("type") == "MSK_CLOUDS":
                return self._qi_mask_abs_path(i.text)
        else:
            raise KeyError("no MSK_CLOUDS item found in metadata")

    def _band_mask(self, qi_mask=None, band=None) -> str:
        if band not in self._bands:
            raise KeyError(f"band must be one of {self._bands}, not {band}")
        band_id = self.band_name_to_id(band)
        msk = QI_MASKS[qi_mask]
        for masks in self.xml_root.iter("Pixel_Level_QI"):
            if masks.get("geometry") == "FULL_RESOLUTION":
                for mask_path in masks:
                    if mask_path.get("type") == msk:
                        band = int(mask_path.get("bandId"))
                        if band == band_id:
                            return self._qi_mask_abs_path(mask_path.text)
                else:
                    raise KeyError(f"no {msk} for band {band_id} found in metadata")
        else:
            raise KeyError(f"no {msk} for band {band_id} found in metadata")

    def band_qi_mask(self, qi_mask=None, band=None) -> str:
        if qi_mask not in QI_MASKS:
            raise KeyError(f"invalid QI mask: {qi_mask}")
        if qi_mask not in self.processing_baseline.available_masks():
            raise DeprecationWarning(
                f"QI mask '{qi_mask}' not available for this product"
            )
        return self._band_mask(qi_mask=qi_mask, band=band)


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

    _PRE_0400_MASK_PATHS = {
        "clouds": "MSK_CLOUDS_B00.gml",
        "defective": "MSK_DEFECT_{band}.gml",
        "saturated": "MSK_SATURA_{band}.gml",
        "nodata": "MSK_NODATA_{band}.gml",
        "detector_footprints": "MSK_DETFOO_{band}.gml",
        "technical_quality": "MSK_TECQUA_{band}.gml",
    }
    _POST_0400_MASK_PATHS = {
        "clouds": "CLASSI_B00.jp2",
        "detector_footprints": "DETFOO_{band}.jp2",
        "technical_quality": "QUALIT_{band}.jp2",
    }

    def __init__(
        self,
        metadata_xml: str,
        alternative_metadata_baseurl: str = "sentinel-s2-l2a",
        protocol: str = "s3",
        baseline_version="04.00",
        **kwargs,
    ):
        _basedir = os.path.dirname(metadata_xml)
        tileinfo_metadata = f"{_basedir}/tileinfo_metadata.json"
        with fs_from_path(tileinfo_metadata).open(tileinfo_metadata) as src:
            tileinfo = json.loads(src.read())
            self._path = tileinfo["path"]
        self._utm_zone, self._latitude_band, self._grid_square = _basedir.split("/")[
            -6:-3
        ]
        self._baseurl = alternative_metadata_baseurl
        self._protocol = protocol
        self.processing_baseline = ProcessingBaseline.from_version(baseline_version)
