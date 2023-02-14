from typing import Union

import numpy as np
import numpy.ma as ma
import xarray as xr

# dtypes from https://numpy.org/doc/stable/user/basics.types.html
_NUMPY_FLOAT_DTYPES = [
    np.half,
    np.float16,
    np.single,
    np.double,
    np.longdouble,
    np.csingle,
    np.cdouble,
    np.clongdouble,
]


def xarr_to_masked(
    xarr: Union[xr.Dataset, xr.DataArray], copy: bool = False
) -> ma.MaskedArray:
    """Convert xr.DataArray to ma.MaskedArray."""
    fill_value = xarr.attrs.get("_FillValue")
    if fill_value is None:
        raise ValueError(
            "Cannot create masked_array because DataArray fill value is None"
        )

    if xarr.dtype in _NUMPY_FLOAT_DTYPES:
        return ma.masked_values(xarr, fill_value, copy=copy)
    else:
        return ma.masked_equal(xarr, fill_value, copy=copy)


def masked_to_xarr(
    masked_arr: ma.MaskedArray,
    nodataval: Union[float, None] = None,
    name: Union[str, None] = None,
    x_axis_name: str = "x",
    y_axis_name: str = "y",
    attrs: dict = dict(),
) -> xr.DataArray:
    """Convert ma.MaskedArray to xr.DataArray."""

    # nodata handling is weird.
    #
    # xr.DataArray cannot hold a masked_array but will turn it into
    # a usual NumPy array, replacing the masked values with np.nan.
    # However, this also seems to change the dtype to float32 which
    # is not desirable.
    #
    #
    nodataval = masked_arr.fill_value if nodataval is None else nodataval
    attrs = dict() if attrs is None else attrs
    return xr.DataArray(
        data=masked_arr.filled(nodataval),
        dims=(x_axis_name, y_axis_name),
        name=name,
        attrs=dict(attrs, _FillValue=nodataval),
    )
