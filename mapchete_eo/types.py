import datetime
from dataclasses import dataclass
from enum import Enum
from typing import List, Union

from affine import Affine
from mapchete.types import Bounds
from rasterio.crs import CRS
from rasterio.transform import array_bounds
from tilematrix import Shape


class GeodataType(str, Enum):
    vector = "vector"
    raster = "raster"


class MergeMethod(str, Enum):
    """Available methods to merge assets from multiple items."""

    first = "first"
    average = "average"


NodataVal = Union[int, None]
NodataVals = Union[List[NodataVal], NodataVal]
DateLike = Union[str, datetime.date]
DateTimeLike = Union[DateLike, datetime.datetime]


class Grid:
    def __init__(self, transform: Affine, height: int, width: int, crs: CRS):
        self.transform = transform
        self.height = height
        self.width = width
        self.crs = crs
        self.bounds = Bounds(*array_bounds(self.height, self.width, self.transform))
        self.shape = Shape(self.height, self.width)

    @staticmethod
    def from_obj(obj):
        if hasattr(obj, "transform"):
            transform = obj.transform
        else:
            transform = obj.affine
        return Grid(transform, obj.height, obj.width, obj.crs)


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
