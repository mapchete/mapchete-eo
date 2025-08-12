"""

Original LICENSE:

MIT License

Copyright (c) 2016 Florian Roscheck

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
OR OTHER DEALINGS IN THE SOFTWARE.

Overview
--------

.. currentmodule:: blend_modes.blending_functions

.. autosummary::
    :nosignatures:

    addition
    darken_only
    difference
    divide
    dodge
    grain_extract
    grain_merge
    hard_light
    lighten_only
    multiply
    normal
    overlay
    screen
    soft_light
    subtract
"""

import numpy as np
from typing import Callable
from mapchete_eo.image_operations.blend_modes.type_checks import (
    assert_image_format,
    assert_opacity,
)


class BlendBase:
    def __init__(
        self,
        opacity=1.0,
        disable_type_checks=False,
        dtype=np.float16,
        fcn_name="BlendBase",
    ):
        self.opacity = opacity
        self.disable_type_checks = disable_type_checks
        self.dtype = dtype
        self.fcn_name = fcn_name

    def _prepare(self, src: np.ndarray, dst: np.ndarray):
        if not self.disable_type_checks:
            assert_image_format(src, fcn_name=self.fcn_name, arg_name="src")
            assert_image_format(dst, fcn_name=self.fcn_name, arg_name="dst")
            assert_opacity(self.opacity, fcn_name=self.fcn_name)
        if src.dtype != self.dtype:
            src = src.astype(self.dtype)
        if dst.dtype != self.dtype:
            dst = dst.astype(self.dtype)
        return src, dst

    def blend(self, src: np.ndarray, dst: np.ndarray, blend_func: Callable):
        src, dst = self._prepare(src, dst)
        blended = blend_func(src, dst)
        result = (blended * self.opacity) + (dst * (1 - self.opacity))
        return np.clip(result, 0, 1).astype(self.dtype)


def make_blend_function(blend_func: Callable):
    # This function returns a wrapper that uses a shared BlendBase instance
    base = BlendBase()

    def func(
        src: np.ndarray,
        dst: np.ndarray,
        opacity: float = 1.0,
        disable_type_checks: bool = False,
        dtype: np.dtype = np.float16,
    ) -> np.ndarray:
        # If parameters differ from base, create new BlendBase (rare)
        if (
            opacity != base.opacity
            or disable_type_checks != base.disable_type_checks
            or dtype != base.dtype
        ):
            base_local = BlendBase(opacity, disable_type_checks, dtype)
            return base_local.blend(src, dst, blend_func)
        return base.blend(src, dst, blend_func)

    return func


normal = make_blend_function(lambda s, d: s)
multiply = make_blend_function(lambda s, d: s * d)
screen = make_blend_function(lambda s, d: 1 - (1 - s) * (1 - d))
darken_only = make_blend_function(lambda s, d: np.minimum(s, d))
lighten_only = make_blend_function(lambda s, d: np.maximum(s, d))
difference = make_blend_function(lambda s, d: np.abs(d - s))
subtract = make_blend_function(lambda s, d: np.clip(d - s, 0, 1))


def divide_blend(s: np.ndarray, d: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        res = np.true_divide(d, s)
        res[~np.isfinite(res)] = 0
        return np.clip(res, 0, 1)


divide = make_blend_function(divide_blend)


def grain_extract_blend(s: np.ndarray, d: np.ndarray) -> np.ndarray:
    return np.clip(d - s + 0.5, 0, 1)


grain_extract = make_blend_function(grain_extract_blend)


def grain_merge_blend(s: np.ndarray, d: np.ndarray) -> np.ndarray:
    return np.clip(d + s - 0.5, 0, 1)


grain_merge = make_blend_function(grain_merge_blend)


def overlay_blend(s: np.ndarray, d: np.ndarray) -> np.ndarray:
    mask = d <= 0.5
    result = np.empty_like(d)
    result[mask] = 2 * s[mask] * d[mask]
    result[~mask] = 1 - 2 * (1 - s[~mask]) * (1 - d[~mask])
    return np.clip(result, 0, 1)


overlay = make_blend_function(overlay_blend)


def hard_light_blend(s: np.ndarray, d: np.ndarray) -> np.ndarray:
    mask = s <= 0.5
    result = np.empty_like(d)
    result[mask] = 2 * s[mask] * d[mask]
    result[~mask] = 1 - 2 * (1 - s[~mask]) * (1 - d[~mask])
    return np.clip(result, 0, 1)


hard_light = make_blend_function(hard_light_blend)


def soft_light_blend(s: np.ndarray, d: np.ndarray) -> np.ndarray:
    result = (1 - 2 * s) * d**2 + 2 * s * d
    return np.clip(result, 0, 1)


soft_light = make_blend_function(soft_light_blend)


def dodge_blend(s: np.ndarray, d: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        res = np.true_divide(d, 1 - s)
        res[~np.isfinite(res)] = 1
        return np.clip(res, 0, 1)


dodge = make_blend_function(dodge_blend)


def burn_blend(s: np.ndarray, d: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        res = 1 - np.true_divide(1 - d, s)
        res[~np.isfinite(res)] = 0
        return np.clip(res, 0, 1)


burn = make_blend_function(burn_blend)


def addition_blend(s: np.ndarray, d: np.ndarray) -> np.ndarray:
    return np.clip(s + d, 0, 1)


addition = make_blend_function(addition_blend)
