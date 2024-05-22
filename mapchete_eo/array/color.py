import numpy as np
import numpy.ma as ma


def color_array(shape: tuple, hex_color: str):
    colors = hex_to_rgb(hex_color)
    return ma.masked_array(
        [np.full(shape, color, dtype=np.uint8) for color in colors],
        mask=ma.zeros((len(colors), *shape)),
    )


def hex_to_rgb(hex_color):
    """
    Convert hex color to tuple of RGB(A) colors.

    e.g. "#FFFFFF" --> (255, 255, 255) or "#00FF00FF" --> (0, 255, 0, 255)
    """
    channels = iter(hex_color.lstrip("#"))
    return tuple(int("".join(channel), 16) for channel in zip(channels, channels))


def outlier_pixels(
    arr: np.ndarray,
    axis: int = 0,
    range_threshold: int = 100,
) -> np.ndarray:
    """Detect outlier pixels containing extreme colors."""
    return arr.max(axis=axis) - arr.min(axis=axis) >= range_threshold
