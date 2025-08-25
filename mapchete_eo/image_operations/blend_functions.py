"""

Original LICENSE:

MIT License

Copyright (c) 2016 Florian Roscheck

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation th
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
OR OTHER DEALINGS IN THE SOFTWARE.

"""

import numpy as np


def _compose_alpha(fg: np.ndarray, bg: np.ndarray, opacity: float):
    """Calculate alpha composition ratio between two images."""

    comp_alpha = np.minimum(fg[:, :, 3], bg[:, :, 3]) * opacity
    new_alpha = fg[:, :, 3] + (1.0 - fg[:, :, 3]) * comp_alpha
    np.seterr(divide="ignore", invalid="ignore")
    ratio = comp_alpha / new_alpha
    ratio[np.isnan(ratio)] = 0.0
    return ratio


def normal(fg: np.ndarray, bg: np.ndarray, opacity: float):
    """Apply "normal" blending mode of a layer on an image.

    See Also:
        Find more information on `Wikipedia <https://en.wikipedia.org/wiki/Alpha_compositing#Description>`__.

    Args:
      fg(3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0): Layer to be blended with image
      bg(3-dimensional numpy array of floats (r/g/b/a) in range 0-255.0): Image to be blended upon
      opacity(float): Desired opacity of layer for blending
      disable_type_checks(bool): Whether type checks within the function should be disabled. Disabling the checks may
        yield a slight performance improvement, but comes at the cost of user experience. If you are certain that
        you are passing in the right arguments, you may set this argument to 'True'. Defaults to 'False'.

    Returns:
      3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0: Blended image
    """

    # Extract alpha-channels and apply opacity
    fg_alp = np.expand_dims(fg[:, :, 3], 2)  # alpha of b, prepared for broadcasting
    bg_alp = (
        np.expand_dims(bg[:, :, 3], 2) * opacity
    )  # alpha of a, prepared for broadcasting

    # Blend images
    with np.errstate(divide="ignore", invalid="ignore"):
        img_out = (bg[:, :, :3] * bg_alp + fg[:, :, :3] * fg_alp * (1 - bg_alp)) / (
            bg_alp + fg_alp * (1 - bg_alp)
        )
        img_out[np.isnan(img_out)] = 0  # replace NaNs with 0

    # Blend alpha
    cout_alp = bg_alp + fg_alp * (1 - bg_alp)

    # Combine image and alpha
    img_out = np.dstack((img_out, cout_alp))

    np.nan_to_num(img_out, copy=False)

    return img_out


def soft_light(fg: np.ndarray, bg: np.ndarray, opacity: float):
    """Apply soft light blending mode of a layer on an image.

    See Also:
        Find more information on
        `Wikipedia <https://en.wikipedia.org/w/index.php?title=Blend_modes&oldid=747749280#Soft_Light>`__.

    Args:
      fg(3-dimensional numpy array of floats (r/g/b/a) in range 0-255.0): Image to be blended upon
      bg(3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0): Layer to be blended with image
      opacity(float): Desired opacity of layer for blending
      disable_type_checks(bool): Whether type checks within the function should be disabled. Disabling the checks may
        yield a slight performance improvement, but comes at the cost of user experience. If you are certain that
        you are passing in the right arguments, you may set this argument to 'True'. Defaults to 'False'.

    Returns:
      3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0: Blended image

    """

    ratio = _compose_alpha(fg, bg, opacity)

    # The following code does this:
    #   multiply = fg[:, :, :3]*bg[:, :, :3]
    #   screen = 1.0 - (1.0-fg[:, :, :3])*(1.0-bg[:, :, :3])
    #   comp = (1.0 - fg[:, :, :3]) * multiply + fg[:, :, :3] * screen
    #   ratio_rs = np.reshape(np.repeat(ratio,3),comp.shape)
    #   img_out = comp*ratio_rs + fg[:, :, :3] * (1.0-ratio_rs)

    comp = (1.0 - fg[:, :, :3]) * fg[:, :, :3] * bg[:, :, :3] + fg[:, :, :3] * (
        1.0 - (1.0 - fg[:, :, :3]) * (1.0 - bg[:, :, :3])
    )

    ratio_rs = np.reshape(
        np.repeat(ratio, 3), [comp.shape[0], comp.shape[1], comp.shape[2]]
    )
    img_out = comp * ratio_rs + fg[:, :, :3] * (1.0 - ratio_rs)
    img_out = np.nan_to_num(
        np.dstack((img_out, fg[:, :, 3]))
    )  # add alpha channel and replace nans
    return img_out


def lighten_only(fg: np.ndarray, bg: np.ndarray, opacity: float):
    """Apply lighten only blending mode of a layer on an image.

    See Also:
        Find more information on
        `Wikipedia <https://en.wikipedia.org/w/index.php?title=Blend_modes&oldid=747749280#Lighten_Only>`__.

    Args:
      fg(3-dimensional numpy array of floats (r/g/b/a) in range 0-255.0): Image to be blended upon
      bg(3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0): Layer to be blended with image
      opacity(float): Desired opacity of layer for blending
      disable_type_checks(bool): Whether type checks within the function should be disabled. Disabling the checks may
        yield a slight performance improvement, but comes at the cost of user experience. If you are certain that
        you are passing in the right arguments, you may set this argument to 'True'. Defaults to 'False'.

    Returns:
      3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0: Blended image

    """

    ratio = _compose_alpha(fg, bg, opacity)

    comp = np.maximum(fg[:, :, :3], bg[:, :, :3])

    ratio_rs = np.reshape(
        np.repeat(ratio, 3), [comp.shape[0], comp.shape[1], comp.shape[2]]
    )
    img_out = comp * ratio_rs + fg[:, :, :3] * (1.0 - ratio_rs)
    img_out = np.nan_to_num(
        np.dstack((img_out, fg[:, :, 3]))
    )  # add alpha channel and replace nans
    return img_out


def screen(fg: np.ndarray, bg: np.ndarray, opacity: float):
    """Apply screen blending mode of a layer on an image.

    See Also:
        Find more information on
        `Wikipedia <https://en.wikipedia.org/w/index.php?title=Blend_modes&oldid=747749280#Screen>`__.

    Args:
      fg(3-dimensional numpy array of floats (r/g/b/a) in range 0-255.0): Image to be blended upon
      bg(3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0): Layer to be blended with image
      opacity(float): Desired opacity of layer for blending
      disable_type_checks(bool): Whether type checks within the function should be disabled. Disabling the checks may
        yield a slight performance improvement, but comes at the cost of user experience. If you are certain that
        you are passing in the right arguments, you may set this argument to 'True'. Defaults to 'False'.

    Returns:
      3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0: Blended image

    """

    ratio = _compose_alpha(fg, bg, opacity)

    comp = 1.0 - (1.0 - fg[:, :, :3]) * (1.0 - bg[:, :, :3])

    ratio_rs = np.reshape(
        np.repeat(ratio, 3), [comp.shape[0], comp.shape[1], comp.shape[2]]
    )
    img_out = comp * ratio_rs + fg[:, :, :3] * (1.0 - ratio_rs)
    img_out = np.nan_to_num(
        np.dstack((img_out, fg[:, :, 3]))
    )  # add alpha channel and replace nans
    return img_out


def dodge(fg: np.ndarray, bg: np.ndarray, opacity: float):
    """Apply dodge blending mode of a layer on an image.

    See Also:
        Find more information on
        `Wikipedia <https://en.wikipedia.org/w/index.php?title=Blend_modes&oldid=747749280#Dodge_and_burn>`__.

    Args:
      fg(3-dimensional numpy array of floats (r/g/b/a) in range 0-255.0): Image to be blended upon
      bg(3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0): Layer to be blended with image
      opacity(float): Desired opacity of layer for blending
      disable_type_checks(bool): Whether type checks within the function should be disabled. Disabling the checks may
        yield a slight performance improvement, but comes at the cost of user experience. If you are certain that
        you are passing in the right arguments, you may set this argument to 'True'. Defaults to 'False'.

    Returns:
      3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0: Blended image

    """

    ratio = _compose_alpha(fg, bg, opacity)

    comp = np.minimum(fg[:, :, :3] / (1.0 - bg[:, :, :3]), 1.0)

    ratio_rs = np.reshape(
        np.repeat(ratio, 3), [comp.shape[0], comp.shape[1], comp.shape[2]]
    )
    img_out = comp * ratio_rs + fg[:, :, :3] * (1.0 - ratio_rs)
    img_out = np.nan_to_num(
        np.dstack((img_out, fg[:, :, 3]))
    )  # add alpha channel and replace nans
    return img_out


def addition(fg: np.ndarray, bg: np.ndarray, opacity: float):
    """Apply addition blending mode of a layer on an image.

    See Also:
        Find more information on
        `Wikipedia <https://en.wikipedia.org/w/index.php?title=Blend_modes&oldid=747749280#Addition>`__.

    Args:
      fg(3-dimensional numpy array of floats (r/g/b/a) in range 0-255.0): Image to be blended upon
      bg(3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0): Layer to be blended with image
      opacity(float): Desired opacity of layer for blending
      disable_type_checks(bool): Whether type checks within the function should be disabled. Disabling the checks may
        yield a slight performance improvement, but comes at the cost of user experience. If you are certain that
        you are passing in the right arguments, you may set this argument to 'True'. Defaults to 'False'.

    Returns:
      3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0: Blended image

    """

    ratio = _compose_alpha(fg, bg, opacity)

    comp = fg[:, :, :3] + bg[:, :, :3]

    ratio_rs = np.reshape(
        np.repeat(ratio, 3), [comp.shape[0], comp.shape[1], comp.shape[2]]
    )
    img_out = np.clip(comp * ratio_rs + fg[:, :, :3] * (1.0 - ratio_rs), 0.0, 1.0)
    img_out = np.nan_to_num(
        np.dstack((img_out, fg[:, :, 3]))
    )  # add alpha channel and replace nans
    return img_out


def darken_only(fg: np.ndarray, bg: np.ndarray, opacity: float):
    """Apply darken only blending mode of a layer on an image.

    See Also:
        Find more information on
        `Wikipedia <https://en.wikipedia.org/w/index.php?title=Blend_modes&oldid=747749280#Darken_Only>`__.

    Args:
      fg(3-dimensional numpy array of floats (r/g/b/a) in range 0-255.0): Image to be blended upon
      bg(3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0): Layer to be blended with image
      opacity(float): Desired opacity of layer for blending
      disable_type_checks(bool): Whether type checks within the function should be disabled. Disabling the checks may
        yield a slight performance improvement, but comes at the cost of user experience. If you are certain that
        you are passing in the right arguments, you may set this argument to 'True'. Defaults to 'False'.

    Returns:
      3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0: Blended image

    """

    ratio = _compose_alpha(fg, bg, opacity)

    comp = np.minimum(fg[:, :, :3], bg[:, :, :3])

    ratio_rs = np.reshape(
        np.repeat(ratio, 3), [comp.shape[0], comp.shape[1], comp.shape[2]]
    )
    img_out = comp * ratio_rs + fg[:, :, :3] * (1.0 - ratio_rs)
    img_out = np.nan_to_num(
        np.dstack((img_out, fg[:, :, 3]))
    )  # add alpha channel and replace nans
    return img_out


def multiply(fg: np.ndarray, bg: np.ndarray, opacity: float):
    """Apply multiply blending mode of a layer on an image.

    See Also:
        Find more information on
        `Wikipedia <https://en.wikipedia.org/w/index.php?title=Blend_modes&oldid=747749280#Multiply>`__.

    Args:
      fg(3-dimensional numpy array of floats (r/g/b/a) in range 0-255.0): Image to be blended upon
      bg(3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0): Layer to be blended with image
      opacity(float): Desired opacity of layer for blending
      disable_type_checks(bool): Whether type checks within the function should be disabled. Disabling the checks may
        yield a slight performance improvement, but comes at the cost of user experience. If you are certain that
        you are passing in the right arguments, you may set this argument to 'True'. Defaults to 'False'.

    Returns:
      3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0: Blended image

    """

    ratio = _compose_alpha(fg, bg, opacity)

    comp = np.clip(bg[:, :, :3] * fg[:, :, :3], 0.0, 1.0)

    ratio_rs = np.reshape(
        np.repeat(ratio, 3), [comp.shape[0], comp.shape[1], comp.shape[2]]
    )
    img_out = comp * ratio_rs + fg[:, :, :3] * (1.0 - ratio_rs)
    img_out = np.nan_to_num(
        np.dstack((img_out, fg[:, :, 3]))
    )  # add alpha channel and replace nans
    return img_out


def hard_light(fg: np.ndarray, bg: np.ndarray, opacity: float):
    """Apply hard light blending mode of a layer on an image.

    See Also:
        Find more information on
        `Wikipedia <https://en.wikipedia.org/w/index.php?title=Blend_modes&oldid=747749280#Hard_Light>`__.

    Args:
      fg(3-dimensional numpy array of floats (r/g/b/a) in range 0-255.0): Image to be blended upon
      bg(3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0): Layer to be blended with image
      opacity(float): Desired opacity of layer for blending
      disable_type_checks(bool): Whether type checks within the function should be disabled. Disabling the checks may
        yield a slight performance improvement, but comes at the cost of user experience. If you are certain that
        you are passing in the right arguments, you may set this argument to 'True'. Defaults to 'False'.

    Returns:
      3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0: Blended image

    """

    ratio = _compose_alpha(fg, bg, opacity)

    comp = np.greater(bg[:, :, :3], 0.5) * np.minimum(
        1.0 - ((1.0 - fg[:, :, :3]) * (1.0 - (bg[:, :, :3] - 0.5) * 2.0)),
        1.0,
    ) + np.logical_not(np.greater(bg[:, :, :3], 0.5)) * np.minimum(
        fg[:, :, :3] * (bg[:, :, :3] * 2.0), 1.0
    )

    ratio_rs = np.reshape(
        np.repeat(ratio, 3), [comp.shape[0], comp.shape[1], comp.shape[2]]
    )
    img_out = comp * ratio_rs + fg[:, :, :3] * (1.0 - ratio_rs)
    img_out = np.nan_to_num(
        np.dstack((img_out, fg[:, :, 3]))
    )  # add alpha channel and replace nans
    return img_out


def difference(fg: np.ndarray, bg: np.ndarray, opacity: float):
    """Apply difference blending mode of a layer on an image.

    See Also:
        Find more information on
        `Wikipedia <https://en.wikipedia.org/w/index.php?title=Blend_modes&oldid=747749280#Difference>`__.

    Args:
      fg(3-dimensional numpy array of floats (r/g/b/a) in range 0-255.0): Image to be blended upon
      bg(3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0): Layer to be blended with image
      opacity(float): Desired opacity of layer for blending
      disable_type_checks(bool): Whether type checks within the function should be disabled. Disabling the checks may
        yield a slight performance improvement, but comes at the cost of user experience. If you are certain that
        you are passing in the right arguments, you may set this argument to 'True'. Defaults to 'False'.

    Returns:
      3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0: Blended image

    """

    ratio = _compose_alpha(fg, bg, opacity)

    comp = fg[:, :, :3] - bg[:, :, :3]
    comp[comp < 0.0] *= -1.0

    ratio_rs = np.reshape(
        np.repeat(ratio, 3), [comp.shape[0], comp.shape[1], comp.shape[2]]
    )
    img_out = comp * ratio_rs + fg[:, :, :3] * (1.0 - ratio_rs)
    img_out = np.nan_to_num(
        np.dstack((img_out, fg[:, :, 3]))
    )  # add alpha channel and replace nans
    return img_out


def subtract(fg: np.ndarray, bg: np.ndarray, opacity: float):
    """Apply subtract blending mode of a layer on an image.

    See Also:
        Find more information on
        `Wikipedia <https://en.wikipedia.org/w/index.php?title=Blend_modes&oldid=747749280#Subtract>`__.

    Args:
      fg(3-dimensional numpy array of floats (r/g/b/a) in range 0-255.0): Image to be blended upon
      bg(3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0): Layer to be blended with image
      opacity(float): Desired opacity of layer for blending
      disable_type_checks(bool): Whether type checks within the function should be disabled. Disabling the checks may
        yield a slight performance improvement, but comes at the cost of user experience. If you are certain that
        you are passing in the right arguments, you may set this argument to 'True'. Defaults to 'False'.

    Returns:
      3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0: Blended image

    """

    ratio = _compose_alpha(fg, bg, opacity)

    comp = fg[:, :, :3] - bg[:, :, :3]

    ratio_rs = np.reshape(
        np.repeat(ratio, 3), [comp.shape[0], comp.shape[1], comp.shape[2]]
    )
    img_out = np.clip(comp * ratio_rs + fg[:, :, :3] * (1.0 - ratio_rs), 0.0, 1.0)
    img_out = np.nan_to_num(
        np.dstack((img_out, fg[:, :, 3]))
    )  # add alpha channel and replace nans
    return img_out


def grain_extract(fg: np.ndarray, bg: np.ndarray, opacity: float):
    """Apply grain extract blending mode of a layer on an image.

    See Also:
        Find more information in the `GIMP Documentation <https://docs.gimp.org/en/gimp-concepts-layer-modes.html>`__.

    Args:
      fg(3-dimensional numpy array of floats (r/g/b/a) in range 0-255.0): Image to be blended upon
      bg(3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0): Layer to be blended with image
      opacity(float): Desired opacity of layer for blending
      disable_type_checks(bool): Whether type checks within the function should be disabled. Disabling the checks may
        yield a slight performance improvement, but comes at the cost of user experience. If you are certain that
        you are passing in the right arguments, you may set this argument to 'True'. Defaults to 'False'.

    Returns:
      3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0: Blended image

    """

    ratio = _compose_alpha(fg, bg, opacity)

    comp = np.clip(fg[:, :, :3] - bg[:, :, :3] + 0.5, 0.0, 1.0)

    ratio_rs = np.reshape(
        np.repeat(ratio, 3), [comp.shape[0], comp.shape[1], comp.shape[2]]
    )
    img_out = comp * ratio_rs + fg[:, :, :3] * (1.0 - ratio_rs)
    img_out = np.nan_to_num(
        np.dstack((img_out, fg[:, :, 3]))
    )  # add alpha channel and replace nans
    return img_out


def grain_merge(fg: np.ndarray, bg: np.ndarray, opacity: float):
    """Apply grain merge blending mode of a layer on an image.

    See Also:
        Find more information in the `GIMP Documentation <https://docs.gimp.org/en/gimp-concepts-layer-modes.html>`__.

    Args:
      fg(3-dimensional numpy array of floats (r/g/b/a) in range 0-255.0): Image to be blended upon
      bg(3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0): Layer to be blended with image
      opacity(float): Desired opacity of layer for blending
      disable_type_checks(bool): Whether type checks within the function should be disabled. Disabling the checks may
        yield a slight performance improvement, but comes at the cost of user experience. If you are certain that
        you are passing in the right arguments, you may set this argument to 'True'. Defaults to 'False'.

    Returns:
      3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0: Blended image

    """

    ratio = _compose_alpha(fg, bg, opacity)

    comp = np.clip(fg[:, :, :3] + bg[:, :, :3] - 0.5, 0.0, 1.0)

    ratio_rs = np.reshape(
        np.repeat(ratio, 3), [comp.shape[0], comp.shape[1], comp.shape[2]]
    )
    img_out = comp * ratio_rs + fg[:, :, :3] * (1.0 - ratio_rs)
    img_out = np.nan_to_num(
        np.dstack((img_out, fg[:, :, 3]))
    )  # add alpha channel and replace nans
    return img_out


def divide(fg: np.ndarray, bg: np.ndarray, opacity: float):
    """Apply divide blending mode of a layer on an image.

    See Also:
        Find more information on
        `Wikipedia <https://en.wikipedia.org/w/index.php?title=Blend_modes&oldid=747749280#Divide>`__.

    Args:
      fg(3-dimensional numpy array of floats (r/g/b/a) in range 0-255.0): Image to be blended upon
      bg(3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0): Layer to be blended with image
      opacity(float): Desired opacity of layer for blending
      disable_type_checks(bool): Whether type checks within the function should be disabled. Disabling the checks may
        yield a slight performance improvement, but comes at the cost of user experience. If you are certain that
        you are passing in the right arguments, you may set this argument to 'True'. Defaults to 'False'.

    Returns:
      3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0: Blended image

    """

    ratio = _compose_alpha(fg, bg, opacity)

    comp = np.minimum(
        (256.0 / 255.0 * fg[:, :, :3]) / (1.0 / 255.0 + bg[:, :, :3]),
        1.0,
    )

    ratio_rs = np.reshape(
        np.repeat(ratio, 3), [comp.shape[0], comp.shape[1], comp.shape[2]]
    )
    img_out = comp * ratio_rs + fg[:, :, :3] * (1.0 - ratio_rs)
    img_out = np.nan_to_num(
        np.dstack((img_out, fg[:, :, 3]))
    )  # add alpha channel and replace nans
    return img_out


def overlay(fg: np.ndarray, bg: np.ndarray, opacity: float):
    """Apply overlay blending mode of a layer on an image.

    Note:
        The implementation of this method was changed in version 2.0.0. Previously, it would be identical to the
        soft light blending mode. Now, it resembles the implementation on Wikipedia. You can still use the soft light
        blending mode if you are looking for backwards compatibility.

    See Also:
        Find more information on
        `Wikipedia <https://en.wikipedia.org/w/index.php?title=Blend_modes&oldid=868545948#Overlay>`__.

    Args:
      fg(3-dimensional numpy array of floats (r/g/b/a) in range 0-255.0): Image to be blended upon
      bg(3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0): Layer to be blended with image
      opacity(float): Desired opacity of layer for blending
      disable_type_checks(bool): Whether type checks within the function should be disabled. Disabling the checks may
        yield a slight performance improvement, but comes at the cost of user experience. If you are certain that
        you are passing in the right arguments, you may set this argument to 'True'. Defaults to 'False'.

    Returns:
      3-dimensional numpy array of floats (r/g/b/a) in range 0.0-255.0: Blended image

    """

    ratio = _compose_alpha(fg, bg, opacity)

    comp = np.less(fg[:, :, :3], 0.5) * (
        2 * fg[:, :, :3] * bg[:, :, :3]
    ) + np.greater_equal(fg[:, :, :3], 0.5) * (
        1 - (2 * (1 - fg[:, :, :3]) * (1 - bg[:, :, :3]))
    )

    ratio_rs = np.reshape(
        np.repeat(ratio, 3), [comp.shape[0], comp.shape[1], comp.shape[2]]
    )
    img_out = comp * ratio_rs + fg[:, :, :3] * (1.0 - ratio_rs)
    img_out = np.nan_to_num(
        np.dstack((img_out, fg[:, :, 3]))
    )  # add alpha channel and replace nans
    return img_out
