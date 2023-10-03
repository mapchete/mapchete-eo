from typing import List, Optional, Union

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
        return ma.masked_values(xarr, fill_value, copy=copy, shrink=False)
    else:
        out = ma.masked_equal(xarr, fill_value, copy=copy)
        # in case of a shrinked mask we have to expand it to the full array shape
        if not isinstance(out.mask, np.ndarray):
            out.mask = np.full(out.mask.shape, out.mask, dtype=bool)
        return out


def masked_to_xarr(
    masked_arr: ma.MaskedArray,
    nodataval: Union[float, None] = None,
    name: Union[str, None] = None,
    x_axis_name: str = "x",
    y_axis_name: str = "y",
    attrs: dict = dict(),
) -> xr.DataArray:
    """Convert 2D ma.MaskedArray to xr.DataArray."""

    # nodata handling is weird.
    #
    # xr.DataArray cannot hold a masked_array but will turn it into
    # a usual NumPy array, replacing the masked values with np.nan.
    # However, this also seems to change the dtype to float32 which
    # is not desirable.

    nodataval = masked_arr.fill_value if nodataval is None else nodataval
    attrs = dict() if attrs is None else attrs
    return xr.DataArray(
        data=masked_arr.filled(nodataval),
        dims=(x_axis_name, y_axis_name),
        name=name,
        attrs=dict(attrs, _FillValue=nodataval),
    )


def masked_to_xarr_slice(
    slice_array: ma.MaskedArray,
    slice_name: str,
    band_names: List[str],
    slice_attrs: Optional[dict] = None,
    band_axis_name: str = "bands",
    x_axis_name: str = "x",
    y_axis_name: str = "y",
) -> xr.DataArray:
    """Convert a 3D masked array to a xr.DataArray."""
    return xr.Dataset(
        data_vars={
            # within each slice Dataset, there are DataArrays for each band
            band_name: masked_to_xarr(
                band_array,
                name=slice_name,
                x_axis_name=x_axis_name,
                y_axis_name=y_axis_name,
            )
            for band_name, band_array in zip(band_names, slice_array)
        },
        coords={},
        attrs=slice_attrs,
        # finally, the slice Dataset will be converted into a DataArray itself
    ).to_stacked_array(
        new_dim=band_axis_name,
        sample_dims=(x_axis_name, y_axis_name),
        name=slice_name,
    )


def masked_to_xarr_ds(
    masked_arr: ma.MaskedArray,
    slice_names: List[str],
    band_names: List[str],
    coords: Optional[dict] = None,
    slices_attrs: Optional[List[Union[dict, None]]] = None,
    slice_axis_name: str = "time",
    band_axis_name: str = "bands",
    x_axis_name: str = "x",
    y_axis_name: str = "y",
) -> xr.Dataset:
    """Convert a 4D masked array to a xr.Dataset."""
    slices_attrs = [None for _ in slice_names] if slices_attrs is None else slices_attrs
    return xr.Dataset(
        data_vars={
            # every slice gets its own xarray Dataset
            slice_name: masked_to_xarr_slice(
                slice_array,
                slice_name,
                band_names,
                slice_attrs=slice_attrs,
                band_axis_name=band_axis_name,
                x_axis_name=x_axis_name,
                y_axis_name=y_axis_name,
            )
            for slice_name, slice_attrs, slice_array in zip(
                slice_names,
                slices_attrs,
                masked_arr,
            )
        },
        coords=coords,
    ).transpose(slice_axis_name, band_axis_name, x_axis_name, y_axis_name)
