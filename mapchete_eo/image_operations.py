from typing import Optional, Tuple

import numpy as np
import numpy.ma as ma
from numpy.typing import DTypeLike
from rasterio.dtypes import dtype_ranges

from mapchete_eo.types import NodataVal


def dtype_scale(
    bands: ma.MaskedArray,
    nodata: Optional[NodataVal] = None,
    out_dtype: Optional[DTypeLike] = np.uint8,
    max_source_value: float = 10000.0,
    max_output_value: Optional[float] = None,
) -> ma.MaskedArray:
    """
    (1) normalize array from range [0:max_value] to range [0:1]
    (2) multiply with out_values to create range [0:out_values]
    (3) clip to [1:out_values] to avoid rounding errors where band value can
    accidentally become nodata (0)
    (4) create masked array with burnt in nodata values and original nodata mask
    """
    out_dtype = np.dtype(out_dtype)

    if max_output_value is None:
        max_output_value = np.iinfo(out_dtype).max

    if nodata is None:
        nodata = 0

    return ma.masked_where(
        bands == nodata,
        np.where(
            bands.mask,
            nodata,
            np.clip(
                (bands.astype("float16", copy=False) / max_source_value)
                * max_output_value,
                1,
                max_output_value,
            ),
        ),
    )


def linear_normalization(
    bands: np.ndarray,
    bands_minmax_values: Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]] = (
        (5, 3350),
        (0, 3150),
        (0, 3200),
    ),
    out_dtype: str = "uint8",
    out_min: Optional[int] = None,
) -> ma.MaskedArray:
    """
    Scale and normalize bands to individual minimum and maximum values.

    From eox_preprocessing.image_utils

    See: https://en.wikipedia.org/wiki/Normalization_(image_processing)

    Parameters
    ----------
    bands : np.ndarray
        Input bands as a 3D array.
    bands_minmax_values : list of lists
        Individual minimum and maximum values for each band. Must have the same length as
        number of bands.
    out_min : float or int
        Override dtype minimum. Useful when nodata value is equal to dtype minimum (e.g. 0
        at uint8). In that case out_min can be set to 1.

    Returns
    -------
    scaled bands : ma.MaskedArray
    """
    if len(bands_minmax_values) != bands.shape[0]:
        raise ValueError("bands and bands_minmax_values must have the same length")
    try:
        if out_min is None:
            out_min, out_max = dtype_ranges[out_dtype]
        else:
            out_max = dtype_ranges[out_dtype][1]
    except KeyError:
        raise KeyError("invalid out_dtype: %s" % out_dtype)

    # Clip the Input values first to avoid awkward data
    bands = np.stack(
        [
            np.where(
                np.where(b > b_max, b_max, b) < b_min,
                b_min,
                np.where(b > b_max, b_max, b),
            )
            for b, (b_min, b_max) in zip(bands, bands_minmax_values)
        ]
    )

    lin_normalized = np.clip(
        np.stack(
            [
                (b - b_min) * (out_max / (b_max - b_min)) + out_min
                for b, (b_min, b_max) in zip(bands, bands_minmax_values)
            ]
        ),
        out_min,
        out_max,
    ).astype(out_dtype, copy=False)

    # (2) clip and return using the original nodata mask
    if isinstance(bands, ma.MaskedArray):
        return ma.masked_array(
            data=lin_normalized, mask=bands.mask, fill_value=bands.fill_value
        )
    else:
        return lin_normalized
