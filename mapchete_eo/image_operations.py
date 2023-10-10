import logging
from typing import Optional, Tuple, Union

import cv2
import numpy as np
import numpy.ma as ma
from mapchete import Timer
from numpy.typing import DTypeLike
from rasterio.dtypes import dtype_ranges
from rasterio.features import rasterize, shapes
from rasterio.fill import fillnodata as rio_fillnodata
from scipy.ndimage.filters import convolve
from shapely.geometry import shape

from mapchete_eo.types import NodataVal

logger = logging.getLogger(__name__)


def color_correct(
    rgb: Union[ma.MaskedArray, np.array],
    gamma: float = 1.15,
    clahe_clip_limit: float = 1.25,
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
    clahe = cv2.createCLAHE(clipLimit=clahe_clip_limit, tileGridSize=(32, 32))
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
    v = np.where((v / 255 * gamma) * 255 >= 255, 255, (v / 255 * gamma) * 255)
    # Saturation
    s = s * saturation
    # add all new HSV values into output
    imghsv = cv2.merge([h, s, v]).astype(np.uint8)
    corrected = cv2.cvtColor(imghsv, cv2.COLOR_HSV2BGR)
    corrected = np.clip(
        np.swapaxes(corrected, 2, 0),
        1,
        255,  # clip valid values to 1 and 255 to avoid accidental nodata values
    ).astype(np.uint8, copy=False)

    return ma.masked_array(data=corrected, mask=rgb.mask, fill_value=rgb.fill_value)


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
    )


def linear_normalization(
    bands: Union[ma.MaskedArray, np.ndarray],
    bands_minmax_values: Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]] = (
        (5, 3350),
        (0, 3150),
        (0, 3200),
    ),
    out_dtype: str = "uint8",
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
        if out_min is None:
            out_min, out_max = dtype_ranges[out_dtype]
        else:
            out_max = dtype_ranges[out_dtype][1]
    except KeyError:
        raise KeyError("invalid out_dtype: %s" % out_dtype)

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


def fillnodata(
    bands: list,
    method: str = "patches",
    max_patch_size: int = 2,
    max_nodata_neighbors: int = 0,
    max_search_distance: int = 10,
    smoothing_iterations: int = 0,
) -> ma.MaskedArray:
    """
    Interpolate nodata areas up to a given size.

    This function uses the nodata mask to determine contingent nodata areas. Patches
    up to a certain size are then interpolated using rasterio.fill.fillnodata.

    Parameters
    ----------
    bands : ma.MaskedArray
        Input bands as a 3D array.
    method : str
        Method how to select areas to interpolate. (default: patch_size)
            - all: interpolate all nodata areas
            - patch_size: only interpolate areas up to a certain size. (defined by
                max_patch_size)
            - nodata_neighbors: only interpolate single nodata pixel.
    max_patch_size : int
        Maximum patch size in pixels which is going to be interpolated in "patch_size"
        method.
    max_nodata_neighbors : int
        Maximum number of nodata neighbor pixels in "nodata_neighbors" method.
    max_search_distance : float
        The maxmimum number of pixels to search in all directions to find values to
        interpolate from.
    smoothing_iterations : int
        The number of 3x3 smoothing filter passes to run.

    Returns
    -------
    filled bands : ma.MaskedArray
    """
    if not isinstance(bands, ma.MaskedArray):
        raise TypeError("bands must be a ma.MaskedArray")
    methods = ["all", "patch_size", "nodata_neighbors"]
    if method not in methods:
        raise ValueError("method must be one of %s", ", ".join(methods))

    def _interpolate(bands, max_search_distance, smoothing_iterations):
        return np.stack(
            [
                rio_fillnodata(
                    band.data,
                    mask=~band.mask,
                    max_search_distance=max_search_distance,
                    smoothing_iterations=smoothing_iterations,
                )
                for band in bands
            ]
        )

    if bands.mask.any():
        if method == "all":
            logger.debug("interpolate pixel values in all nodata areas")
            return ma.masked_array(
                data=_interpolate(bands, max_search_distance, smoothing_iterations),
                mask=np.zeros(bands.shape),
            )

        if method == "patch_size":
            logger.debug(
                "interpolate pixel values in nodata areas smaller than or equal %s pixel",
                max_patch_size,
            )
            with Timer() as t:
                patches = [
                    (p, v)
                    for p, v in shapes(bands.mask[0].astype(np.uint8))
                    if v == 1 and shape(p).area <= (max_patch_size)
                ]
            logger.debug("found %s small nodata patches in %s", len(patches), t)
            if patches:
                interpolation_mask = rasterize(
                    patches,
                    out_shape=bands[0].data.shape,
                ).astype(bool)
                # create masked aray using original mask with removed small patches
                return ma.masked_array(
                    data=_interpolate(bands, max_search_distance, smoothing_iterations),
                    mask=bands.mask ^ np.stack([interpolation_mask for _ in bands]),
                )

        if method == "nodata_neighbors":
            kernel = np.array(
                [
                    [0, 1, 0],
                    [1, 0, 1],
                    [0, 1, 0],
                ]
            )
            # count occurances of masked neighbor pixels
            number_mask = bands[0].mask.astype(np.uint8)
            count_mask = convolve(number_mask, kernel)
            # use interpolation on nodata values where there are no neighbor pixels
            interpolation_mask = (count_mask <= max_nodata_neighbors) & bands[0].mask
            # create masked aray using original mask with removed small patches
            return ma.masked_array(
                data=_interpolate(bands, max_search_distance, smoothing_iterations),
                mask=bands.mask ^ np.stack([interpolation_mask for _ in bands]),
            )

    # if nothing was masked or no small patches could be found, return original data
    return bands
