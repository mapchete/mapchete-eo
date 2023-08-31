"""
A path mapper maps from an metadata XML file to additional metadata
on a given archive or a local SAFE file.
"""
import logging
import xml.etree.ElementTree as etree
from functools import cached_property
from typing import Union

from mapchete.path import MPath

from mapchete_eo.io import open_xml
from mapchete_eo.platforms.sentinel2.path_mappers.base import S2PathMapper
from mapchete_eo.platforms.sentinel2.processing_baseline import ProcessingBaseline
from mapchete_eo.platforms.sentinel2.types import (
    BandQIMask,
    L2ABand,
    ProductQIMask,
    ProductQIMaskResolution,
)

logger = logging.getLogger(__name__)


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
        resolution: ProductQIMaskResolution = ProductQIMaskResolution["60m"],
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
        self, resolution: ProductQIMaskResolution = ProductQIMaskResolution["60m"]
    ) -> MPath:
        # TODO: handle resolution
        return self.product_qi_mask(ProductQIMask.cloud_probability)

    def snow_probability_mask(
        self, resolution: ProductQIMaskResolution = ProductQIMaskResolution["60m"]
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
