import numpy as np
import numpy.ma as ma
from typing import Tuple


# Bandpass Adjustment for Sentinel-2B
# I asked chatGPT and they pointed me to and gave me this table for Sentinel-2B:
# https://sentiwiki.copernicus.eu/web/document-library#Library-S2-PDS
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

S2B_BAND_ADJUSTMENT_PARAMS = {
    1: (0.996, 0.002),
    2: (1.001, -0.002),
    3: (0.999, 0.001),
    4: (1.001, -0.003),
    5: (0.998, 0.004),
    6: (0.997, 0.005),
    7: (1.000, 0.000),
    8: (0.999, 0.001),
    9: (0.998, 0.004),
    10: (0.996, 0.006),
    11: (0.997, 0.002),
    12: (0.998, 0.003),
}


def sentinel2b_bandpass_adjustment_band(
    band_arr: ma.MaskedArray, bandpass_params: Tuple[float, float]
) -> np.ndarray:
    return band_arr * bandpass_params[0] + bandpass_params[1]
