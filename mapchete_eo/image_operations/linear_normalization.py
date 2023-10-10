from typing import Optional, Tuple

import numpy as np
import numpy.ma as ma
from numpy.typing import DTypeLike
from rasterio.dtypes import dtype_ranges


def linear_normalization(
    bands: ma.MaskedArray,
    bands_minmax_values: Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]] = (
        (5, 3350),
        (0, 3150),
        (0, 3200),
    ),
    out_dtype: DTypeLike = np.uint8,
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
        if isinstance(out_dtype, str):
            dtype_str = out_dtype
        else:
            dtype_str = str(out_dtype).split(".")[1].split("'")[0]
        if out_min is None:
            out_min, out_max = dtype_ranges[dtype_str]
        else:
            out_max = dtype_ranges[dtype_str][1]
    except KeyError:
        raise KeyError(f"invalid out_dtype: {out_dtype}")

    # Clip the Input values first to avoid awkward data
    clipped_bands = np.stack(
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
                for b, (b_min, b_max) in zip(clipped_bands, bands_minmax_values)
            ]
        ),
        out_min,
        out_max,
    ).astype(out_dtype, copy=False)

    # (2) clip and return using the original nodata mask
    return ma.MaskedArray(
        data=lin_normalized, mask=bands.mask, fill_value=bands.fill_value
    )
