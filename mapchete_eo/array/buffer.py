from typing import Optional

import numpy as np
import numpy.ma as ma
from numpy.typing import DTypeLike
from scipy.ndimage import binary_dilation


def buffer_array(
    array: ma.MaskedArray, buffer: int = 0, out_array_dtype: Optional[DTypeLike] = None
):
    if out_array_dtype is None:
        out_array_dtype = array.dtype
    if buffer == 0:
        return array.astype(out_array_dtype, copy=False)

    return binary_dilation(array, iterations=buffer).astype(out_array_dtype, copy=False)
