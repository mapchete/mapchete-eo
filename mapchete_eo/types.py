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


class Grid:
    def __init__(self, transform: Affine, height: int, width: int, crs: CRS):
        self.transform = transform
        self.height = height
        self.width = width
        self.crs = crs
        self.bounds = Bounds(*array_bounds(self.height, self.width, self.transform))
        self.shape = Shape(self.height, self.width)

    @classmethod
    def from_obj(obj):
        return Grid(obj.transform, obj.height, obj.width, obj.crs)
