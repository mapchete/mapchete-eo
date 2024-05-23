import logging

import numpy as np
from PIL import Image, ImageFilter
from rasterio.plot import reshape_as_image, reshape_as_raster
from scipy import ndimage

logger = logging.getLogger(__name__)


# filters for 8 bit data:
#########################

FILTERS = {
    "blur": ImageFilter.BLUR,
    "contour": ImageFilter.CONTOUR,
    "detail": ImageFilter.DETAIL,
    "edge_enhance": ImageFilter.EDGE_ENHANCE,
    "edge_enhance_more": ImageFilter.EDGE_ENHANCE_MORE,
    "emboss": ImageFilter.EMBOSS,
    "find_edges": ImageFilter.FIND_EDGES,
    "sharpen": ImageFilter.SHARPEN,
    "smooth": ImageFilter.SMOOTH,
    "smooth_more": ImageFilter.SMOOTH_MORE,
}

FILTER_FUNCTIONS = {
    "unsharp_mask": ImageFilter.UnsharpMask,
    "median": ImageFilter.MedianFilter,
    "gaussian_blur": ImageFilter.GaussianBlur,
}


def _apply_filter(arr: np.ndarray, img_filter: str, **kwargs) -> np.ndarray:
    if arr.dtype != "uint8":
        raise TypeError("input array type must be uint8")
    if arr.ndim != 3:
        raise TypeError("input array must be 3-dimensional")
    if arr.shape[0] != 3:
        raise TypeError("input array must have exactly three bands")
    if img_filter in FILTERS:
        return np.clip(
            reshape_as_raster(
                Image.fromarray(reshape_as_image(arr)).filter(FILTERS[img_filter])
            ),
            1,
            255,
        ).astype("uint8", copy=False)
    elif img_filter in FILTER_FUNCTIONS:
        return np.clip(
            reshape_as_raster(
                Image.fromarray(reshape_as_image(arr)).filter(
                    FILTER_FUNCTIONS[img_filter](**kwargs)
                )
            ),
            1,
            255,
        ).astype("uint8", copy=False)
    else:
        raise KeyError(f"{img_filter} not found")


def blur(arr: np.ndarray) -> np.ndarray:
    """
    Apply PIL blur filter to array and return.

    Parameters
    ----------
    arr : 3-dimensional uint8 NumPy array

    Returns
    -------
    NumPy array
    """
    return _apply_filter(arr, "blur")


def contour(arr: np.ndarray) -> np.ndarray:
    """
    Apply PIL contour filter to array and return.

    Parameters
    ----------
    arr : 3-dimensional uint8 NumPy array

    Returns
    -------
    NumPy array
    """
    return _apply_filter(arr, "contour")


def detail(arr: np.ndarray) -> np.ndarray:
    """
    Apply PIL detail filter to array and return.

    Parameters
    ----------
    arr : 3-dimensional uint8 NumPy array

    Returns
    -------
    NumPy array
    """
    return _apply_filter(arr, "detail")


def edge_enhance(arr: np.ndarray) -> np.ndarray:
    """
    Apply PIL edge_enhance filter to array and return.

    Parameters
    ----------
    arr : 3-dimensional uint8 NumPy array

    Returns
    -------
    NumPy array
    """
    return _apply_filter(arr, "edge_enhance")


def edge_enhance_more(arr: np.ndarray) -> np.ndarray:
    """
    Apply PIL edge_enhance_more filter to array and return.

    Parameters
    ----------
    arr : 3-dimensional uint8 NumPy array

    Returns
    -------
    NumPy array
    """
    return _apply_filter(arr, "edge_enhance_more")


def emboss(arr: np.ndarray) -> np.ndarray:
    """
    Apply PIL emboss filter to array and return.

    Parameters
    ----------
    arr : 3-dimensional uint8 NumPy array

    Returns
    -------
    NumPy array
    """
    return _apply_filter(arr, "emboss")


def find_edges(arr: np.ndarray) -> np.ndarray:
    """
    Apply PIL find_edges filter to array and return.

    Parameters
    ----------
    arr : 3-dimensional uint8 NumPy array

    Returns
    -------
    NumPy array
    """
    return _apply_filter(arr, "find_edges")


def sharpen(arr: np.ndarray) -> np.ndarray:
    """
    Apply PIL sharpen filter to array and return.

    Parameters
    ----------
    arr : 3-dimensional uint8 NumPy array

    Returns
    -------
    NumPy array
    """
    return _apply_filter(arr, "sharpen")


def smooth(arr: np.ndarray) -> np.ndarray:
    """
    Apply PIL smooth filter to array and return.

    Parameters
    ----------
    arr : 3-dimensional uint8 NumPy array

    Returns
    -------
    NumPy array
    """
    return _apply_filter(arr, "smooth")


def smooth_more(arr: np.ndarray) -> np.ndarray:
    """
    Apply PIL smooth_more filter to array and return.

    Parameters
    ----------
    arr : 3-dimensional uint8 NumPy array

    Returns
    -------
    NumPy array
    """
    return _apply_filter(arr, "smooth_more")


def unsharp_mask(
    arr: np.ndarray, radius: int = 2, percent: float = 150, threshold: float = 3
) -> np.ndarray:
    """
    Apply PIL UnsharpMask filter to array and return.

    Parameters
    ----------
    arr : 3-dimensional uint8 NumPy array

    Returns
    -------
    NumPy array
    """
    return _apply_filter(
        arr, "unsharp_mask", radius=radius, percent=percent, threshold=threshold
    )


def median(arr: np.ndarray, size: int = 3) -> np.ndarray:
    """
    Apply PIL MedianFilter to array and return.

    Parameters
    ----------
    arr : 3-dimensional uint8 NumPy array

    Returns
    -------
    NumPy array
    """
    return _apply_filter(arr, "median", size=size)


def gaussian_blur(arr: np.ndarray, radius: int = 2) -> np.ndarray:
    """
    Apply PIL GaussianBlur to array and return.

    Parameters
    ----------
    arr : 3-dimensional uint8 NumPy array

    Returns
    -------
    NumPy array
    """
    return _apply_filter(arr, "gaussian_blur", radius=radius)


# filters for 16 bit data:
##########################


def sharpen_16bit(arr: np.ndarray) -> np.ndarray:
    # kernel_3x3_highpass = np.array([
    #     0, -1, 0,
    #     -1, 5, -1,
    #     0, -1, 0
    # ]).reshape((3, 3))
    # kernel_3x3_highpass = np.array([
    #     0, -1/4, 0,
    #     -1/4, 2, -1/4,
    #     0, -1/4, 0
    # ]).reshape((3, 3))
    # kernel_5x5_highpass = np.array([
    #     0, -1, -1, -1, 0,
    #     -1, -2, -4, 2, -1,
    #     -1, -4, 13, -4, -1,
    #     -1, 2, -4, 2, -1,
    #     0, -1, -1, -1, 0
    # ]).reshape((5, 5))
    # kernel_mean = np.array([
    #     1, 1, 1,
    #     1, 1, 1,
    #     1, 1, 1
    # ]).reshape((3, 3))
    # kernel = np.array([
    #     [1, 1, 1],
    #     [1, 1, 0],
    #     [1, 0, 0]
    # ]).reshape((3, 3))
    # kernel = np.array([
    #     0, -1, 0,
    #     -1, 8, -1,
    #     0, -1, 0
    # ]).reshape((3, 3))
    # Various High Pass Filters
    # b = ndimage.minimum_filter(b, 3)
    # b = ndimage.percentile_filter(b, 50, 3)
    # imgsharp = ndimage.convolve(b_smoothed, kernel_3x3_highpass, mode='nearest')
    # imgsharp = ndimage.median_filter(imgsharp, 2)
    # imgsharp = reshape_as_raster(np.asarray(imgsharp))
    # Official SciPy unsharpen mask filter not working

    # Unshapen Mask Filter, working version as the one above is not working
    return np.stack(
        [
            ndimage.percentile_filter(
                b
                + (b - ndimage.percentile_filter(b, 35, arr.shape[0], mode="nearest")),
                45,
                2,
                mode="nearest",
            )
            for b in arr
        ]
    ).astype(arr.dtype, copy=False)
