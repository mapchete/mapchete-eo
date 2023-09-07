from enum import Enum


class GeodataType(str, Enum):
    vector = "vector"
    raster = "raster"


class MergeMethod(str, Enum):
    """Available methods to merge assets from multiple items."""

    first = "first"
    average = "average"
