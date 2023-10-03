from dataclasses import dataclass
from typing import Any, Optional, Union

from pydantic import BaseModel


class ProductMaskTypes(BaseModel):
    """Mapping between mask type and respective metadata.xml type key."""

    classification: Optional[str] = None
    cloud_probability: Optional[str] = None
    snow_probability: Optional[str] = None


class BandMaskTypes(BaseModel):
    """Mapping between band mask type and respective metadata.xml type key."""

    technical_quality: Optional[str] = None
    detector_footprints: Optional[str] = None
    # deprecated since 04.00
    # nodata: Optional[str] = None
    # defect: Optional[str] = None
    # saturated: Optional[str] = None


class ItemMapping(BaseModel):
    """Configuration of processing baseline keys in metadata.xml."""

    product_mask_types: ProductMaskTypes
    band_mask_types: BandMaskTypes
    band_mask_extension: str


# Available product mask types from PB 00.01 until 03.01.
# "classification" mask was provided as GML, the other two as JP2.
# Cloud probability and snow probability are available in two separate files for
# 20m and 60m.
pre_0400 = ItemMapping(
    product_mask_types=ProductMaskTypes(
        classification="MSK_CLOUDS",
        cloud_probability="MSK_CLDPRB",
        snow_probability="MSK_SNWPRB",
    ),
    band_mask_types=BandMaskTypes(
        technical_quality="MSK_TECQUA",
        detector_footprints="MSK_DETFOO",
    ),
    band_mask_extension="gml",
)


# Available product mask types from PB 04.00 onwards.
# Cloud probability and snow probability are available in two separate files for
# 20m and 60m.
post_0400 = ItemMapping(
    product_mask_types=ProductMaskTypes(
        classification="MSK_CLASSI",
        cloud_probability="MSK_CLDPRB",
        snow_probability="MSK_SNWPRB",
    ),
    band_mask_types=BandMaskTypes(
        technical_quality="MSK_QUALIT",
        detector_footprints="MSK_DETFOO",
    ),
    band_mask_extension="jp2",
)


@dataclass
class BaselineVersion:
    """Helper for Processing Baseline versions."""

    major: int
    minor: int
    level: str

    @staticmethod
    def from_string(version: str) -> "BaselineVersion":
        major, minor = map(int, version.split("."))
        if major < 2:
            level = "L1C"
        # everything below 02.06 is Level 1C
        elif major == 2 and minor <= 6:
            level = "L1C"
        else:
            level = "L2A"
        return BaselineVersion(major, minor, level)

    @staticmethod
    def from_inp(inp: Union[str, "BaselineVersion"]) -> "BaselineVersion":
        if isinstance(inp, str):
            return BaselineVersion.from_string(inp)
        elif isinstance(inp, BaselineVersion):
            return inp
        else:
            raise TypeError(f"cannot generate BaselineVersion from input {inp}")

    def __eq__(self, other: Any):
        other = BaselineVersion.from_inp(other)
        return self.major == other.major and self.minor == other.minor

    def __lt__(self, other: Union[str, "BaselineVersion"]):
        other = BaselineVersion.from_inp(other)
        if self.major == other.major:
            return self.minor < other.minor
        else:
            return self.major < other.major

    def __le__(self, other: Union[str, "BaselineVersion"]):
        other = BaselineVersion.from_inp(other)
        if self.major == other.major:
            return self.minor <= other.minor
        else:
            return self.major <= other.major

    def __gt__(self, other: Union[str, "BaselineVersion"]):
        other = BaselineVersion.from_inp(other)
        if self.major == other.major:
            return self.minor > other.minor
        else:
            return self.major > other.major

    def __ge__(self, other: Union[str, "BaselineVersion"]):
        if isinstance(other, str):
            other = BaselineVersion.from_string(other)
        if self.major == other.major:
            return self.minor >= other.minor
        else:
            return self.major >= other.major

    def __str__(self):
        return f"{self.major:02}.{self.minor:02}"


class ProcessingBaseline:
    """Class which combines PB version and metadata.xml keys for QI masks."""

    version: BaselineVersion
    item_mapping: ItemMapping
    product_mask_types: ProductMaskTypes
    band_mask_types: BandMaskTypes
    band_mask_extension: str

    def __init__(self, version: BaselineVersion):
        self.version = version
        if self.version.major < 4:
            self.item_mapping = pre_0400
        else:
            self.item_mapping = post_0400

        self.product_mask_types = self.item_mapping.product_mask_types
        self.band_mask_types = self.item_mapping.band_mask_types
        self.band_mask_extension = self.item_mapping.band_mask_extension

    @staticmethod
    def from_version(version: Union[BaselineVersion, str]) -> "ProcessingBaseline":
        if isinstance(version, BaselineVersion):
            return ProcessingBaseline(version=version)
        else:
            return ProcessingBaseline(version=BaselineVersion.from_string(version))
