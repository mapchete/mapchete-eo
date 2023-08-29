from dataclasses import dataclass
from typing import Any, Set, Union

PRE_0400_MASKS = {
    "clouds",
    "defective",
    "saturated",
    "nodata",
    "detector_footprints",
    "technical_quality",
}
POST_0400_MASKS = {
    "clouds",
    "detector_footprints",
    "technical_quality",
}
PRE_0400_MASK_EXTENSION = "gml"
POST_0400_MASK_EXTENSION = "jp2"


@dataclass
class BaselineVersion:
    """Helper for Processing Baseline versions"""

    major: int
    minor: int
    level: str

    def masks(self) -> set:
        """Return set of available masks for version."""
        if self.major < 4:
            return PRE_0400_MASKS
        else:
            return POST_0400_MASKS

    def qi_band_extension(self) -> str:
        """Return file extension for QI masks."""
        if self.major < 4:
            return PRE_0400_MASK_EXTENSION
        else:
            return POST_0400_MASK_EXTENSION

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


@dataclass
class ProcessingBaseline:
    version: BaselineVersion

    @staticmethod
    def from_version(version: Union[BaselineVersion, str]) -> "ProcessingBaseline":
        if isinstance(version, BaselineVersion):
            return ProcessingBaseline(version=version)
        else:
            return ProcessingBaseline(version=BaselineVersion.from_string(version))

    def available_masks(self) -> Set:
        return self.version.masks()

    def qi_band_extension(self) -> str:
        return self.version.qi_band_extension()
