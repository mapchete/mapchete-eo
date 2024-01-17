import logging

import cv2
import numpy as np
import numpy.ma as ma

logger = logging.getLogger(__name__)


def color_correct(
    rgb: ma.MaskedArray,
    gamma: float = 1.15,
    clahe_flag: bool = True,
    clahe_clip_limit: float = 1.25,
    clahe_tile_grid_size: tuple = (32, 32),
    saturation: float = 3.2,
) -> ma.MaskedArray:
    """
    Return color corrected 8 bit RGB array from 8 bit input RGB.

    Uses rio-color to apply correction.

    Parameters
    ----------
    bands : ma.MaskedArray
        Input bands as a 8bit 3D array.
    gamma : float
        Apply gamma in HSV color space.
    clahe_clip_limit : float
        Common values limit the resulting amplification to between 3 and 4.
        See "Contrast Limited AHE" at:
        https://en.wikipedia.org/wiki/Adaptive_histogram_equalization.
    saturation : float
        Controls the saturation in HSV color space.

    Returns
    -------
    color corrected image : np.ndarray
    """
    if rgb.dtype != "uint8":
        raise TypeError("rgb must be of dtype np.uint8")

    # Some CLAHE info: https://imagej.net/plugins/clahe
    lab = cv2.cvtColor(np.swapaxes(rgb, 0, 2), cv2.COLOR_BGR2LAB).astype(
        np.uint8, copy=False
    )
    lab_planes = list(cv2.split(lab))
    if clahe_flag is True:
        clahe = cv2.createCLAHE(
            clipLimit=clahe_clip_limit, tileGridSize=clahe_tile_grid_size
        )
        lab_planes[0] = clahe.apply(lab_planes[0])
        lab = cv2.merge(lab_planes)
    corrected = np.clip(
        cv2.cvtColor(lab, cv2.COLOR_LAB2BGR),
        1,
        255,  # clip valid values to 1 and 255 to avoid accidental nodata values
    ).astype(np.uint8, copy=False)

    # Brightness
    imghsv = cv2.cvtColor(corrected, cv2.COLOR_BGR2HSV).astype(np.float16)
    (h, s, v) = cv2.split(imghsv)
    v = np.clip(
        np.where((v / 255 * gamma) * 255 >= 255, 255, (v / 255 * gamma) * 255), 1, 255
    )
    # Saturation
    s = np.clip(s * saturation, 1, 255)
    # add all new HSV values into output
    imghsv = cv2.merge([h, s, v]).astype(np.uint8)
    corrected = cv2.cvtColor(imghsv, cv2.COLOR_HSV2BGR)
    corrected = np.clip(
        np.swapaxes(corrected, 2, 0),
        1,
        255,  # clip valid values to 1 and 255 to avoid accidental nodata values
    ).astype(np.uint8, copy=False)

    return ma.masked_array(data=corrected, mask=rgb.mask, fill_value=rgb.fill_value)
