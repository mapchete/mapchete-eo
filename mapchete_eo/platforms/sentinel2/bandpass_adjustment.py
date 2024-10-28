from enum import Enum
from typing import NamedTuple
import numpy as np
import numpy.ma as ma
from numpy.typing import DTypeLike

from pystac import Item

from mapchete_eo.platforms.sentinel2.types import L2ABand


class BandpassAdjustment(NamedTuple):
    slope: float
    intercept: float


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


class L2AS2ABandpassAdjustmentParams(Enum):
    B01 = BandpassAdjustment(0.9959, -0.0002)
    B02 = BandpassAdjustment(0.9778, -0.004)
    B03 = BandpassAdjustment(1.0053, -0.0009)
    B04 = BandpassAdjustment(0.9765, 0.0009)
    B05 = BandpassAdjustment(1.0, 0.0)
    B06 = BandpassAdjustment(1.0, 0.0)
    B07 = BandpassAdjustment(1.0, 0.0)
    B08 = BandpassAdjustment(0.9983, -0.0001)
    B8A = BandpassAdjustment(0.9983, -0.0001)
    B09 = BandpassAdjustment(1.0, 0.0)
    B11 = BandpassAdjustment(0.9987, -0.0011)
    B12 = BandpassAdjustment(1.003, -0.0012)


class L2AS2BBandpassAdjustmentParams(Enum):
    B01 = BandpassAdjustment(0.9959, -0.0002)
    B02 = BandpassAdjustment(0.9778, -0.004)
    B03 = BandpassAdjustment(1.0075, -0.0008)
    B04 = BandpassAdjustment(0.9761, 0.001)
    B05 = BandpassAdjustment(0.998, 0.004)
    B06 = BandpassAdjustment(0.997, 0.005)
    B07 = BandpassAdjustment(1.000, 0.000)
    B08 = BandpassAdjustment(0.9966, 0.000)
    B8A = BandpassAdjustment(0.9966, 0.000)
    B09 = BandpassAdjustment(0.996, 0.006)
    B11 = BandpassAdjustment(1.000, -0.0003)
    B12 = BandpassAdjustment(0.9867, 0.0004)


def item_to_params(
    sentinel2_item: Item,
    l2a_band: L2ABand,
) -> BandpassAdjustment:
    if sentinel2_item.properties["platform"].lower() == "sentinel-2a":
        return L2AS2ABandpassAdjustmentParams[l2a_band.name].value
    elif sentinel2_item.properties["platform"].lower() == "sentinel-2b":
        return L2AS2BBandpassAdjustmentParams[l2a_band.name].value
    else:
        raise TypeError(
            f"cannot determine Sentinel-2 platform from pystac.Item: {sentinel2_item}"
        )


def apply_bandpass_adjustment(
    band_arr: ma.MaskedArray,
    item: Item,
    l2a_band: L2ABand,
    computing_dtype: DTypeLike = np.float32,
    out_dtype: DTypeLike = np.uint16,
) -> ma.MaskedArray:
    params = item_to_params(item, l2a_band)
    return ma.MaskedArray(
        data=(
            np.clip(
                band_arr.astype(computing_dtype, copy=False) / 10000 * params.slope
                + params.intercept,
                0,
                1,
            )
            * 10000
        )
        .astype(out_dtype, copy=False)
        .data,
        mask=band_arr.mask,
        fill_value=band_arr.fill_value,
    )
