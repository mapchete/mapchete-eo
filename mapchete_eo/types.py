from enum import Enum
from typing import List, Union


class GeodataType(str, Enum):
    vector = "vector"
    raster = "raster"


class MergeMethod(str, Enum):
    """Available methods to merge assets from multiple items."""

    first = "first"
    average = "average"


NodataVal = Union[int, None]
NodataVals = Union[List[NodataVal], NodataVal]
