import numpy as np
import numpy.ma as ma
from rasterio.enums import Resampling
from rasterio.warp import reproject


def resample_array(
    in_array=None,
    in_transform=None,
    in_crs=None,
    nodata=0,
    dst_transform=None,
    dst_crs=None,
    dst_shape=None,
    resampling="bilinear",
) -> ma.MaskedArray:
    """Resample array and return as masked array"""
    dst_data = np.empty(dst_shape, in_array.dtype)
    reproject(
        in_array,
        dst_data,
        src_transform=in_transform,
        src_crs=in_crs,
        src_nodata=nodata,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        dst_nodata=nodata,
        resampling=Resampling[resampling],
    )
    return ma.masked_array(
        data=np.nan_to_num(dst_data, nan=nodata),
        mask=ma.masked_invalid(dst_data).mask,
        fill_value=nodata,
    )
