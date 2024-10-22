import numpy as np
import numpy.ma as ma
from numpy.typing import DTypeLike
from typing import Tuple


# Bandpass Adjustment for Sentinel-2
# Try using HLS bandpass adjustmets
# https://hls.gsfc.nasa.gov/algorithms/bandpass-adjustment/
# https://lpdaac.usgs.gov/documents/1698/HLS_User_Guide_V2.pdf
# These are for Sentinel-2B bandpass adjustment; fisrt is slope second is intercept
# out_band = band * slope + intercept
# B1	0.996	0.002
# B2	1.001	-0.002
# B3	0.999	0.001
# B4	1.001	-0.003
# B5	0.998	0.004
# B6	0.997	0.005
# B7	1.000	0.000
# B8	0.999	0.001
# B8A	0.998	0.004
# B9	0.996	0.006
# B10	1.001	-0.001  B10 is not present in Sentinel-2 L2A products ommited in params below
# B11	0.997	0.002
# B12	0.998	0.003

S2A_BAND_ADJUSTMENT_PARAMS = {
    1: (0.9959, -0.0002),
    2: (0.9778, -0.004),
    3: (1.0053, -0.0009),
    4: (0.9765, 0.0009),
    5: (1.0, 0.0),
    6: (1.0, 0.0),
    7: (1.0, 0.0),
    8: (0.9983, -0.0001),
    9: (0.9983, -0.0001),
    10: (1.0, 0.0),
    11: (0.9987, -0.0011),
    12: (1.003, -0.0012),
}

S2B_BAND_ADJUSTMENT_PARAMS = {
    1: (0.9959, -0.0002),
    2: (0.9778, -0.004),
    3: (1.0075, -0.0008),
    4: (0.9761, 0.001),
    5: (0.998, 0.004),
    6: (0.997, 0.005),
    7: (1.000, 0.000),
    8: (0.9966, 0.000),
    9: (0.9966, 0.000),
    10: (0.996, 0.006),
    11: (1.000, -0.0003),
    12: (0.9867, 0.0004),
}


def sentinel2_bandpass_adjustment_band(
    band_arr: ma.MaskedArray,
    bandpass_params: Tuple[float, float],
    computing_dtype: DTypeLike = np.float32,
    out_dtype: DTypeLike = np.uint16,
) -> np.ndarray:
    return (
        (
            band_arr.astype(computing_dtype, copy=False) / 10000 * bandpass_params[0]
            + bandpass_params[1]
        )
        * 10000
    ).astype(out_dtype, copy=False)
