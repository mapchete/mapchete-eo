import logging
from enum import Enum

import numpy as np
import numpy.ma as ma
from mapchete import Timer
from rasterio.features import rasterize, shapes
from rasterio.fill import fillnodata as rio_fillnodata
from scipy.ndimage.filters import convolve
from shapely.geometry import shape

logger = logging.getLogger(__name__)


class FillSelectionMethod(str, Enum):
    all = "all"
    patch_size = "patch_size"
    nodata_neighbors = "nodata_neighbors"


def fillnodata(
    bands: ma.MaskedArray,
    method: FillSelectionMethod = FillSelectionMethod.patch_size,
    max_patch_size: int = 2,
    max_nodata_neighbors: int = 0,
    max_search_distance: float = 10,
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
    if not isinstance(bands, ma.MaskedArray):  # pragma: no cover
        raise TypeError("bands must be a ma.MaskedArray")

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
        if method == FillSelectionMethod.all:
            logger.debug("interpolate pixel values in all nodata areas")
            return ma.masked_array(
                data=_interpolate(bands, max_search_distance, smoothing_iterations),
                mask=np.zeros(bands.shape),
            )

        elif method == FillSelectionMethod.patch_size:
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

        elif method == FillSelectionMethod.nodata_neighbors:
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

        else:  # pragma: no cover
            raise ValueError(f"unknown method: {method}")

    # if nothing was masked or no small patches could be found, return original data
    return bands
