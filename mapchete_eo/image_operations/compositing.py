import logging
from enum import Enum
from typing import Callable, Optional

import blend_modes
import cv2
import numpy as np
import numpy.ma as ma
from mapchete import Timer
from rasterio.plot import reshape_as_image, reshape_as_raster

logger = logging.getLogger(__name__)


def to_rgba(arr: np.ndarray) -> np.ndarray:
    def _expanded_mask(arr: ma.MaskedArray) -> np.ndarray:
        if isinstance(arr.mask, np.bool_):
            return np.full(arr.shape, fill_value=arr.mask, dtype=bool)
        else:
            return arr.mask

    # make sure array is a proper MaskedArray with expanded mask
    if not isinstance(arr, ma.MaskedArray):
        arr = ma.masked_array(arr, mask=np.zeros(arr.shape, dtype=bool))
    if arr.dtype != np.uint8:
        raise TypeError(f"image array must be of type uint8, not {str(arr.dtype)}")
    num_bands = arr.shape[0]
    if num_bands == 1:
        alpha = np.where(~_expanded_mask(arr[0]), 255, 0).astype(np.uint8, copy=False)
        out = np.stack([arr[0], arr[0], arr[0], alpha]).data
    elif num_bands == 2:
        out = np.stack([arr[0], arr[0], arr[0], arr[1]]).data
    elif num_bands == 3:
        alpha = np.where(
            (
                ~_expanded_mask(arr[0])
                & ~_expanded_mask(arr[1])
                & ~_expanded_mask(arr[2])
            ),
            255,
            0,
        ).astype(np.uint8, copy=False)
        out = np.stack([arr[0], arr[1], arr[2], alpha]).data
    elif num_bands == 4:
        out = arr.data
    else:  # pragma: no cover
        raise TypeError(
            f"array must have between one and four bands but has {num_bands}"
        )
    return np.array(out, dtype=np.float16)


def _blend_base(
    bg: np.ndarray, fg: np.ndarray, opacity: float, operation: Callable
) -> ma.MaskedArray:
    # generate RGBA output and run compositing
    out_arr = reshape_as_raster(
        operation(
            reshape_as_image(to_rgba(bg)),
            reshape_as_image(to_rgba(fg)),
            opacity,
            disable_type_checks=True,
        ).astype(np.uint8)
    )
    # generate mask from alpha band
    out_mask = np.where(out_arr[3] == 0, True, False)
    return ma.masked_array(out_arr, mask=np.stack([out_mask for _ in range(4)]))


def normal(bg: np.ndarray, fg: np.ndarray, opacity: float = 1) -> ma.MaskedArray:
    return _blend_base(bg, fg, opacity, blend_modes.normal)


def soft_light(bg: np.ndarray, fg: np.ndarray, opacity: float = 1) -> ma.MaskedArray:
    return _blend_base(bg, fg, opacity, blend_modes.soft_light)


def lighten_only(bg: np.ndarray, fg: np.ndarray, opacity: float = 1) -> ma.MaskedArray:
    return _blend_base(bg, fg, opacity, blend_modes.lighten_only)


def screen(bg: np.ndarray, fg: np.ndarray, opacity: float = 1) -> ma.MaskedArray:
    return _blend_base(bg, fg, opacity, blend_modes.screen)


def dodge(bg: np.ndarray, fg: np.ndarray, opacity: float = 1) -> ma.MaskedArray:
    return _blend_base(bg, fg, opacity, blend_modes.dodge)


def addition(bg: np.ndarray, fg: np.ndarray, opacity: float = 1) -> ma.MaskedArray:
    return _blend_base(bg, fg, opacity, blend_modes.addition)


def darken_only(bg: np.ndarray, fg: np.ndarray, opacity: float = 1) -> ma.MaskedArray:
    return _blend_base(bg, fg, opacity, blend_modes.darken_only)


def multiply(bg: np.ndarray, fg: np.ndarray, opacity: float = 1) -> ma.MaskedArray:
    return _blend_base(bg, fg, opacity, blend_modes.multiply)


def hard_light(bg: np.ndarray, fg: np.ndarray, opacity: float = 1) -> ma.MaskedArray:
    return _blend_base(bg, fg, opacity, blend_modes.hard_light)


def difference(bg: np.ndarray, fg: np.ndarray, opacity: float = 1) -> ma.MaskedArray:
    return _blend_base(bg, fg, opacity, blend_modes.difference)


def subtract(bg: np.ndarray, fg: np.ndarray, opacity: float = 1) -> ma.MaskedArray:
    return _blend_base(bg, fg, opacity, blend_modes.subtract)


def grain_extract(bg: np.ndarray, fg: np.ndarray, opacity: float = 1) -> ma.MaskedArray:
    return _blend_base(bg, fg, opacity, blend_modes.grain_extract)


def grain_merge(bg: np.ndarray, fg: np.ndarray, opacity: float = 1) -> ma.MaskedArray:
    return _blend_base(bg, fg, opacity, blend_modes.grain_merge)


def divide(bg: np.ndarray, fg: np.ndarray, opacity: float = 1) -> ma.MaskedArray:
    return _blend_base(bg, fg, opacity, blend_modes.divide)


def overlay(bg: np.ndarray, fg: np.ndarray, opacity: float = 1) -> ma.MaskedArray:
    return _blend_base(bg, fg, opacity, blend_modes.overlay)


METHODS = {
    "multiply": multiply,
    "normal": normal,
    "soft_light": soft_light,
    "lighten_only": lighten_only,
    "screen": screen,
    "dodge": dodge,
    "addition": addition,
    "darken_only": darken_only,
    "hard_light": hard_light,
    "difference": difference,
    "subtract": subtract,
    "grain_extract": grain_extract,
    "grain_merge": grain_merge,
    "divide": divide,
    "overlay": overlay,
}


def composite(
    method: str, bg: np.ndarray, fg: np.ndarray, opacity: float = 1
) -> ma.MaskedArray:
    return METHODS[method](bg, fg, opacity)


def fuzzy_mask(
    arr: np.ndarray,
    fill_value: float,
    radius: int = 0,
    invert: bool = True,
    dilate: bool = True,
) -> np.ndarray:
    """Create fuzzy mask from binary mask."""
    if arr.ndim == 2:
        arr = np.expand_dims(arr, 0)
    if arr.ndim != 3:
        raise TypeError("array must have exactly three dimensions")
    if arr.shape[0] == 1:
        three_bands = np.stack([arr[0] for _ in range(3)])
    elif arr.shape[0] == 3:
        three_bands = arr
    else:
        raise TypeError(
            f"array must have either one or three bands, not {arr.shape[0]}"
        )
    if invert:
        three_bands = ~three_bands
    # convert mask into an image and set true values to fill value
    # dilate = buffer image using the blur radius
    out = np.multiply(reshape_as_image(three_bands), fill_value, dtype=np.uint8)
    if dilate and radius:
        with Timer() as t:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius, radius))
        logger.debug("dilation kernel generated in %s", t)
        with Timer() as t:
            out = cv2.morphologyEx(out, cv2.MORPH_DILATE, kernel)
        logger.debug("dilation took %s", t)
    # blur and return
    if radius:
        with Timer() as t:
            out = reshape_as_raster(cv2.blur(out, (radius, radius)))[0]
        logger.debug("blur filter took %s", t)
    else:
        out = reshape_as_raster(out)[0]
    if invert:
        return -(out - fill_value).astype(np.uint8)
    return out


class GradientPosition(Enum):
    inside = "inside"
    outside = "outside"
    edge = "edge"


def fuzzy_alpha_mask(
    arr: np.ndarray,
    mask: Optional[np.ndarray] = None,
    radius=0,
    fill_value=255,
    gradient_position=GradientPosition.outside,
) -> np.ndarray:
    """Return an RGBA array with a fuzzy alpha mask."""
    gradient_position = (
        GradientPosition[gradient_position]
        if isinstance(gradient_position, str)
        else gradient_position
    )

    if arr.shape[0] != 3:
        raise TypeError("input array must have exactly three bands")

    if mask is None:
        if not isinstance(arr, ma.MaskedArray):
            raise TypeError(
                "input array must be a numpy MaskedArray or mask must be provided"
            )
        mask = arr.mask

    if gradient_position == GradientPosition.outside:
        fuzzy = fuzzy_mask(
            mask, fill_value=fill_value, radius=radius, invert=False, dilate=True
        )

    elif gradient_position == GradientPosition.inside:
        fuzzy = fuzzy_mask(
            mask, fill_value=fill_value, radius=radius, invert=True, dilate=True
        )

    elif gradient_position == GradientPosition.edge:
        fuzzy = fuzzy_mask(mask, fill_value=fill_value, radius=radius, dilate=False)

    else:  # pragma: no cover
        raise ValueError(f"unknown gradient_position: {gradient_position}")

    # doing this makes sure that originally masked pixels are also fully masked
    # fuzzy[mask[0]] = 255
    return np.concatenate((arr, np.expand_dims(fuzzy, 0)), axis=0)
