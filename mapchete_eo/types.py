from enum import Enum


class GeodataType(str, Enum):
    vector = "vector"
    raster = "raster"
