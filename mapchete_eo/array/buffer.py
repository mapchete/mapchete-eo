from typing import Optional

import numpy as np
from numpy.typing import DTypeLike
from scipy.ndimage import binary_dilation


def buffer_array(
    array: np.ndarray, buffer: int = 0, out_array_dtype: Optional[DTypeLike] = None
) -> np.ndarray:
    if out_array_dtype is None:
        out_array_dtype = array.dtype
    if buffer == 0:
        return array.astype(out_array_dtype, copy=False)

    return binary_dilation(array, iterations=buffer).astype(out_array_dtype, copy=False)
