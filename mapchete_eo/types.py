import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Union


class GeodataType(str, Enum):
    vector = "vector"
    raster = "raster"


class MergeMethod(str, Enum):
    """
    Available methods to merge assets from multiple items.

    first: first pixel value from the list is returned
    average: average value from the list is returned
    all: any consecutive value is added and all collected are returned
    """

    first = "first"
    average = "average"
    all = "all"


DateLike = Union[str, datetime.date]
DateTimeLike = Union[DateLike, datetime.datetime]


@dataclass
class BandLocation:
    """A class representing the location of a specific band."""

    asset_name: str
    band_index: int = 1
    nodataval: float = 0


@dataclass
class TimeRange:
    """A class handling time ranges."""

    start: DateTimeLike
    end: DateTimeLike
