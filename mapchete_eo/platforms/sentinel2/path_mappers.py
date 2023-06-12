"""
A path mapper maps from an metadata XML file to additional metadata
on a given archive or a local SAFE file.
"""

from abc import ABC, abstractmethod
from cached_property import cached_property
from fsspec.exceptions import FSTimeoutError
import logging
from mapchete.path import MPath
from retry import retry
from typing import Union
import xml.etree.ElementTree as etree

from mapchete_eo.platforms.sentinel2.processing_baseline import ProcessingBaseline
from mapchete_eo.platforms.sentinel2.types import QI_MASKS, L2ABand
from mapchete_eo.settings import MP_EO_IO_RETRY_SETTINGS

logger = logging.getLogger(__name__)


@retry(
    logger=logger,
    exceptions=(TimeoutError, FSTimeoutError),
    **MP_EO_IO_RETRY_SETTINGS,
)
def open_xml(path: MPath):
    logger.debug(f"open {path}")
    return etree.fromstring(path.read_text())


class S2PathMapper(ABC):
    """
    Abstract class to help mapping asset paths from metadata.xml to their
    locations of various data archives.

    This is mainly used for additional data like QI masks.
    """

    # All available bands for Sentinel-2 Level 2A.
    _bands = [band.name for band in L2ABand]

    processing_baseline: ProcessingBaseline

    def band_name_to_id(self, band_name) -> int:
        for id, band in enumerate(self._bands):
            if band_name == band:
                return id
        else:
            raise KeyError(f"band name {band_name} not found in {self._bands}")

    @abstractmethod
    def cloud_mask(self) -> MPath:
        ...

    @abstractmethod
    def band_qi_mask(
        self, qi_mask: Union[str, None] = None, band=Union[str, int, None]
    ) -> MPath:
        ...


class XMLMapper(S2PathMapper):
    _cached_xml_root = None

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

    def _qi_mask_abs_path(self, qi_path) -> str:
        return self._metadata_dir / qi_path

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
