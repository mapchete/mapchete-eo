from typing import Optional, Union

import numpy as np
import numpy.ma as ma
from affine import Affine
from mapchete.io.raster import ReferencedRaster
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.warp import reproject
from tilematrix import Shape

from mapchete_eo.protocols import GridProtocol
from mapchete_eo.types import Grid


def resample_array(
    inp: Union[ReferencedRaster, np.ndarray],
    grid: GridProtocol,
    in_transform: Optional[Affine] = None,
    in_crs: Optional[CRS] = None,
    nodata: int = 0,
    resampling: Resampling = Resampling.nearest,
) -> ma.MaskedArray:
    """Resample array and return as masked array"""
    grid = Grid.from_obj(grid)
    if isinstance(inp, ReferencedRaster):
        in_array = inp.data
        in_transform = inp.transform
        in_crs = inp.crs
    elif isinstance(inp, np.ndarray):
        in_array = inp
    else:
        raise TypeError(
            f"input has to either be a mapchete.io.raster.ReferencedRaster or a NumPy array, not {type(inp)}."
        )

    dst_shape: tuple = grid.shape
    if len(in_array.shape) == 3:
        dst_shape = (in_array.shape[0], *grid.shape)

    dst_data = np.empty(dst_shape, in_array.dtype)
    reproject(
        in_array,
        dst_data,
        src_transform=in_transform,
        src_crs=in_crs,
        src_nodata=nodata,
        dst_transform=grid.transform,
        dst_crs=grid.crs,
        dst_nodata=nodata,
        resampling=resampling,
    )
    return ma.masked_array(
        data=np.nan_to_num(dst_data, nan=nodata),
        mask=ma.masked_invalid(dst_data).mask,
        fill_value=nodata,
    )
