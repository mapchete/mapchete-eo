import logging
import math

import numpy as np

logger = logging.getLogger(__name__)


def get_constant_sun_angle(min_lat=None, max_lat=None, **kwargs):
    """
    Calculate constant sun angle between latitudes.

    Returns
    =======
    sun angle in radians : float
    """
    central_lat = min_lat + (max_lat - min_lat) / 2
    return math.radians(_sun_angle(central_lat))


def get_sun_angle_array(min_lat=None, max_lat=None, shape=None):
    """
    Calculate array of sun angles between latitudes.

    Returns
    =======
    sun angle array in radians : np.ndarray
    """
    # return get_constant_sun_angle(min_lat, max_lat)
    height, width = shape
    cell_size = (max_lat - min_lat) / (height + 1)

    # move by half a pixel so pixel centers are represented
    top = max_lat - cell_size / 2

    # generate one column of angles
    angles = [_sun_angle(top - i * cell_size) for i in range(width)]

    # expand column to output shape width
    return np.radians(
        np.array([[i for _ in range(width)] for i in angles], dtype=np.float32)
    )


def _sun_angle(lat):
    """
    Calculate the constant sun zenith angle via 6th polynomial function see HLS.

    See page 13 of:
    https://hls.gsfc.nasa.gov/wp-content/uploads/2019/01/HLS.v1.4.UserGuide_draft_ver3.1.pdf
    """
    # constants used for sun angle calculation
    # See page 13 of:
    # https://hls.gsfc.nasa.gov/wp-content/uploads/2019/01/HLS.v1.4.UserGuide_draft_ver3.1.pdf
    k0 = 31
    k1 = -0.127
    k2 = 0.0119
    k3 = 2.4e-05
    k4 = -9.48e-07
    k5 = -1.95e-09
    k6 = 6.15e-11

    # Constant sun zenith angle 6th polynomial function
    return (
        k0
        + k1 * lat
        + k2 * (lat**2)
        + k4 * (lat**4)
        + k3 * (lat**3)
        + k5 * (lat**5)
        + k6 * (lat**6)
    )
