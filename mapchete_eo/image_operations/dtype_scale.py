from typing import Optional

import numpy as np
import numpy.ma as ma
from mapchete.types import NodataVal
from numpy.typing import DTypeLike


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
    ).astype(out_dtype, copy=False)
