import logging
from typing import Tuple

import cv2
import numpy as np
import numpy.ma as ma
from numpy.typing import DTypeLike
from rasterio.plot import reshape_as_image, reshape_as_raster

from mapchete_eo.image_operations.sigmoidal import sigmoidal

logger = logging.getLogger(__name__)


def color_correct(
    rgb: ma.MaskedArray,
    gamma: float = 1.15,
    clahe_flag: bool = True,
    clahe_clip_limit: float = 1.25,
    clahe_tile_grid_size: Tuple[int, int] = (32, 32),
    sigmoidal_flag: bool = False,
    sigmoidal_constrast: int = 0,
    sigmoidal_bias: float = 0.0,
    saturation: float = 3.2,
    calculations_dtype: DTypeLike = np.float16,
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
    if isinstance(calculations_dtype, str):
        calculations_dtype = np.dtype(getattr(np, calculations_dtype))
    if not isinstance(calculations_dtype, np.dtype):
        raise TypeError(
            f"Harmonization dtype needs to be valid numpy dtype is: {type(calculations_dtype)}"
        )

    if rgb.dtype != "uint8":
        raise TypeError("rgb must be of dtype np.uint8")

    # get and keep original mask
    rgb_src_mask = rgb.mask
    rgb_src_fill_value = rgb.fill_value

    # Move bands to the last axis
    # rgb = np.swapaxes(rgb, 0, 2).astype(np.uint8, copy=False)
    rgb_image = reshape_as_image(rgb)

    # Saturation from OpenVC
    if saturation != 1.0:
        imghsv = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2HSV).astype(
            calculations_dtype, copy=False
        )
        (h, s, v) = cv2.split(imghsv)
        # add all new HSV values into output
        imghsv = cv2.merge([h, np.clip(s * saturation, 1, 255), v]).astype(
            np.uint8, copy=False
        )
        rgb_image = np.clip(
            cv2.cvtColor(imghsv, cv2.COLOR_HSV2RGB),
            1,
            255,  # clip valid values to 1 and 255 to avoid accidental nodata values
        ).astype(np.uint8, copy=False)

    # Sigmodial Contrast and Bias from rio-color
    # Swap bands from last axis to the first one as we are acusstomed to
    # For the sigmodial contrast
    if sigmoidal_flag is True:
        rgb_image = np.clip(
            (
                sigmoidal(
                    np.clip(
                        rgb_image.astype(calculations_dtype, copy=False) / 255,
                        0,
                        1,
                    ).astype(calculations_dtype, copy=False),
                    contrast=sigmoidal_constrast,
                    bias=sigmoidal_bias,
                    out_dtype=calculations_dtype,
                ).astype(calculations_dtype, copy=False)
                * 255
            ),
            1,
            255,
        ).astype(np.uint8, copy=False)

    # Gamma from rio-color
    if gamma != 1.0:
        rgb_image = np.clip(
            ((rgb_image.astype(calculations_dtype) / 255) ** (1.0 / gamma)) * 255,
            1,
            255,
        ).astype(np.uint8, copy=False)

    # CLAHE from OpenVC
    # Some CLAHE info: https://imagej.net/plugins/clahe
    if clahe_flag is True:
        lab = cv2.cvtColor(
            rgb_image.astype(np.uint8, copy=False), cv2.COLOR_RGB2LAB
        ).astype(np.uint8, copy=False)
        lab_planes = list(cv2.split(lab))
        clahe = cv2.createCLAHE(
            clipLimit=clahe_clip_limit, tileGridSize=clahe_tile_grid_size
        )
        lab_planes[0] = clahe.apply(lab_planes[0])
        lab = cv2.merge(lab_planes)
        rgb_image = np.clip(
            cv2.cvtColor(lab, cv2.COLOR_LAB2RGB),
            1,
            255,  # clip valid values to 1 and 255 to avoid accidental nodata values
        ).astype(np.uint8, copy=False)

    # Return array with original mask
    return ma.masked_array(
        data=reshape_as_raster(rgb_image),
        mask=rgb_src_mask,
        fill_value=rgb_src_fill_value,
    )
