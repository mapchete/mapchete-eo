from typing import List, Optional

from rasterio.enums import Resampling
from xarray import Dataset

from mapchete_eo.base import EODataCube
from mapchete_eo.types import MergeMethod


def execute(
    inp: EODataCube,
    assets: Optional[List[str]] = None,
    resampling: Resampling = Resampling.nearest,
    merge_method: MergeMethod = MergeMethod.average,
) -> Dataset:
    """
    Convert EO Data Cube into xarray.
    """
    return inp.read(assets=assets, resampling=resampling, merge_method=merge_method)
