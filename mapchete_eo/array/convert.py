from typing import List, Optional, Union

import numpy as np
import numpy.ma as ma
import xarray as xr
from mapchete.types import NodataVal

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


def to_masked_array(
    xarr: Union[xr.Dataset, xr.DataArray], copy: bool = False
) -> ma.MaskedArray:
    """Convert xr.DataArray to ma.MaskedArray."""
    if isinstance(xarr, xr.Dataset):
        xarr = xarr.to_array()

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


def to_dataarray(
    masked_arr: ma.MaskedArray,
    nodataval: NodataVal = None,
    name: Optional[str] = None,
    band_names: Optional[List[str]] = None,
    band_axis_name: str = "bands",
    x_axis_name: str = "x",
    y_axis_name: str = "y",
    attrs: Optional[dict] = None,
) -> xr.DataArray:
    """
    Convert ma.MaskedArray to xr.DataArray.

    Depending on whether the array is 2D or 3D, the axes will be named accordingly.

    A 2-dimensional array indicates that we only have a spatial x- and y-axis. A
    3rd dimension will be interpreted as bands.
    """
    # nodata handling is weird.
    #
    # xr.DataArray cannot hold a masked_array but will turn it into
    # a usual NumPy array, replacing the masked values with np.nan.
    # However, this also seems to change the dtype to float32 which
    # is not desirable.
    nodataval = masked_arr.fill_value if nodataval is None else nodataval
    attrs = attrs or dict()

    if masked_arr.ndim == 2:
        dims = [x_axis_name, y_axis_name]
        coords = None
    elif masked_arr.ndim == 3:
        bands_count = masked_arr.shape[0]
        band_names = band_names or [f"{band_axis_name}-{i}" for i in range(bands_count)]
        dims = [band_axis_name, x_axis_name, y_axis_name]
        coords = {band_axis_name: band_names}
    else:  # pragma: no cover
        raise TypeError("only a 2D or 3D ma.MaskedArray is allowed.")

    return xr.DataArray(
        data=masked_arr.filled(nodataval),
        dims=dims,
        name=name,
        attrs=dict(attrs, _FillValue=nodataval),
        coords=coords,
    )


def to_dataset(
    masked_arr: ma.MaskedArray,
    nodataval: NodataVal = None,
    slice_names: Optional[List[str]] = None,
    band_names: Optional[List[str]] = None,
    slices_attrs: Optional[List[Union[dict, None]]] = None,
    slice_axis_name: str = "time",
    band_axis_name: str = "bands",
    x_axis_name: str = "x",
    y_axis_name: str = "y",
    attrs: Optional[dict] = None,
):
    """Convert a 3D or 4D ma.MaskedArray to an xarray.Dataset."""
    attrs = attrs or dict()
    nodataval = masked_arr.fill_value if nodataval is None else nodataval

    if masked_arr.ndim == 3:
        bands = masked_arr.shape[0]
        band_names = band_names or [f"{band_axis_name}-{i}" for i in range(bands)]
        raise NotImplementedError()
    elif masked_arr.ndim == 4:
        slices, bands = masked_arr.shape[:2]
        band_names = band_names or [f"{band_axis_name}-{i}" for i in range(bands)]
        slice_names = slice_names or [f"{slice_axis_name}-{i}" for i in range(slices)]
        slices_attrs = (
            [None for _ in range(slices)] if slices_attrs is None else slices_attrs
        )
        coords = {slice_axis_name: slice_names}
        return xr.Dataset(
            data_vars={
                # every slice gets its own xarray Dataset
                slice_name: to_dataarray(
                    slice_array,
                    nodataval=nodataval,
                    band_names=band_names,
                    name=slice_name,
                    attrs=slice_attrs,
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
            attrs=dict(attrs, _FillValue=nodataval),
        ).transpose(slice_axis_name, band_axis_name, x_axis_name, y_axis_name)

    else:  # pragma: no cover
        raise TypeError("only a 3D or 4D ma.MaskedArray is allowed.")


def to_bands_mask(arr: np.ndarray, bands: int = 1) -> np.ndarray:
    """Expands a 2D mask to a full band mask."""
    if arr.ndim != 2:
        raise TypeError("input array has to have exactly 2 dimensions.")
    return np.repeat(
        np.expand_dims(
            arr,
            axis=0,
        ),
        bands,
        axis=0,
    )
