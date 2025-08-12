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
    fcn_name: str  # declare attribute here

    def __init__(
        self,
        opacity: float = 1.0,
        disable_type_checks: bool = False,
        dtype=np.float16,
        fcn_name: str = "BlendBase",
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

    def _blend(self, src: np.ndarray, dst: np.ndarray, blend_func: Callable):
        src, dst = self._prepare(src, dst)
        blended = blend_func(src, dst)
        result = (blended * self.opacity) + (dst * (1 - self.opacity))
        return np.clip(result, 0, 1).astype(self.dtype)


def normal(
    src: np.ndarray,
    dst: np.ndarray,
    opacity: float = 1.0,
    disable_type_checks: bool = False,
    dtype: np.dtype = np.float16,
) -> np.ndarray:
    base = BlendBase(opacity, disable_type_checks, dtype)
    return base._blend(src, dst, lambda s, d: s)


def multiply(
    src: np.ndarray,
    dst: np.ndarray,
    opacity: float = 1.0,
    disable_type_checks: bool = False,
    dtype: np.dtype = np.float16,
) -> np.ndarray:
    base = BlendBase(opacity, disable_type_checks, dtype)
    return base._blend(src, dst, lambda s, d: s * d)


def screen(
    src: np.ndarray,
    dst: np.ndarray,
    opacity: float = 1.0,
    disable_type_checks: bool = False,
    dtype: np.dtype = np.float16,
) -> np.ndarray:
    base = BlendBase(opacity, disable_type_checks, dtype)
    return base._blend(src, dst, lambda s, d: 1 - (1 - s) * (1 - d))


def darken_only(
    src: np.ndarray,
    dst: np.ndarray,
    opacity: float = 1.0,
    disable_type_checks: bool = False,
    dtype: np.dtype = np.float16,
) -> np.ndarray:
    base = BlendBase(opacity, disable_type_checks, dtype)

    def blend(s: np.ndarray, d: np.ndarray) -> np.ndarray:
        return np.minimum(s, d)

    return base._blend(src, dst, blend)


def lighten_only(
    src: np.ndarray,
    dst: np.ndarray,
    opacity: float = 1.0,
    disable_type_checks: bool = False,
    dtype: np.dtype = np.float16,
) -> np.ndarray:
    base = BlendBase(opacity, disable_type_checks, dtype)

    def blend(s: np.ndarray, d: np.ndarray) -> np.ndarray:
        return np.maximum(s, d)

    return base._blend(src, dst, blend)


def difference(
    src: np.ndarray,
    dst: np.ndarray,
    opacity: float = 1.0,
    disable_type_checks: bool = False,
    dtype: np.dtype = np.float16,
) -> np.ndarray:
    base = BlendBase(opacity, disable_type_checks, dtype)

    def blend(s: np.ndarray, d: np.ndarray) -> np.ndarray:
        return np.abs(d - s)

    return base._blend(src, dst, blend)


def subtract(
    src: np.ndarray,
    dst: np.ndarray,
    opacity: float = 1.0,
    disable_type_checks: bool = False,
    dtype: np.dtype = np.float16,
) -> np.ndarray:
    base = BlendBase(opacity, disable_type_checks, dtype)

    def blend(s: np.ndarray, d: np.ndarray) -> np.ndarray:
        return np.clip(d - s, 0, 1)

    return base._blend(src, dst, blend)


def divide(
    src: np.ndarray,
    dst: np.ndarray,
    opacity: float = 1.0,
    disable_type_checks: bool = False,
    dtype: np.dtype = np.float16,
) -> np.ndarray:
    base = BlendBase(opacity, disable_type_checks, dtype)

    def blend(s: np.ndarray, d: np.ndarray) -> np.ndarray:
        with np.errstate(divide="ignore", invalid="ignore"):
            res = np.true_divide(d, s)
            res[~np.isfinite(res)] = 0
            return np.clip(res, 0, 1)

    return base._blend(src, dst, blend)


def grain_extract(
    src: np.ndarray,
    dst: np.ndarray,
    opacity: float = 1.0,
    disable_type_checks: bool = False,
    dtype: np.dtype = np.float16,
) -> np.ndarray:
    base = BlendBase(opacity, disable_type_checks, dtype)

    def blend(s: np.ndarray, d: np.ndarray) -> np.ndarray:
        return np.clip(d - s + 0.5, 0, 1)

    return base._blend(src, dst, blend)


def grain_merge(
    src: np.ndarray,
    dst: np.ndarray,
    opacity: float = 1.0,
    disable_type_checks: bool = False,
    dtype: np.dtype = np.float16,
) -> np.ndarray:
    base = BlendBase(opacity, disable_type_checks, dtype)

    def blend(s: np.ndarray, d: np.ndarray) -> np.ndarray:
        return np.clip(d + s - 0.5, 0, 1)

    return base._blend(src, dst, blend)


def overlay(
    src: np.ndarray,
    dst: np.ndarray,
    opacity: float = 1.0,
    disable_type_checks: bool = False,
    dtype: np.dtype = np.float16,
) -> np.ndarray:
    base = BlendBase(opacity, disable_type_checks, dtype)

    def blend(s: np.ndarray, d: np.ndarray) -> np.ndarray:
        mask = d <= 0.5
        result = np.empty_like(d)
        result[mask] = 2 * s[mask] * d[mask]
        result[~mask] = 1 - 2 * (1 - s[~mask]) * (1 - d[~mask])
        return np.clip(result, 0, 1)

    return base._blend(src, dst, blend)


def hard_light(
    src: np.ndarray,
    dst: np.ndarray,
    opacity: float = 1.0,
    disable_type_checks: bool = False,
    dtype: np.dtype = np.float16,
) -> np.ndarray:
    base = BlendBase(opacity, disable_type_checks, dtype)

    def blend(s: np.ndarray, d: np.ndarray) -> np.ndarray:
        mask = s <= 0.5
        result = np.empty_like(d)
        result[mask] = 2 * s[mask] * d[mask]
        result[~mask] = 1 - 2 * (1 - s[~mask]) * (1 - d[~mask])
        return np.clip(result, 0, 1)

    return base._blend(src, dst, blend)


def soft_light(
    src: np.ndarray,
    dst: np.ndarray,
    opacity: float = 1.0,
    disable_type_checks: bool = False,
    dtype: np.dtype = np.float16,
) -> np.ndarray:
    base = BlendBase(opacity, disable_type_checks, dtype)

    def blend(s: np.ndarray, d: np.ndarray) -> np.ndarray:
        result = (1 - 2 * s) * d**2 + 2 * s * d
        return np.clip(result, 0, 1)

    return base._blend(src, dst, blend)


def dodge(
    src: np.ndarray,
    dst: np.ndarray,
    opacity: float = 1.0,
    disable_type_checks: bool = False,
    dtype: np.dtype = np.float16,
) -> np.ndarray:
    base = BlendBase(opacity, disable_type_checks, dtype)

    def blend(s: np.ndarray, d: np.ndarray) -> np.ndarray:
        with np.errstate(divide="ignore", invalid="ignore"):
            res = np.true_divide(d, 1 - s)
            res[~np.isfinite(res)] = 1
            return np.clip(res, 0, 1)

    return base._blend(src, dst, blend)


def burn(
    src: np.ndarray,
    dst: np.ndarray,
    opacity: float = 1.0,
    disable_type_checks: bool = False,
    dtype: np.dtype = np.float16,
) -> np.ndarray:
    base = BlendBase(opacity, disable_type_checks, dtype)

    def blend(s: np.ndarray, d: np.ndarray) -> np.ndarray:
        with np.errstate(divide="ignore", invalid="ignore"):
            res = 1 - np.true_divide(1 - d, s)
            res[~np.isfinite(res)] = 0
            return np.clip(res, 0, 1)

    return base._blend(src, dst, blend)


def addition(
    src: np.ndarray,
    dst: np.ndarray,
    opacity: float = 1.0,
    disable_type_checks: bool = False,
    dtype: np.dtype = np.float16,
) -> np.ndarray:
    base = BlendBase(opacity, disable_type_checks, dtype)

    def blend(s: np.ndarray, d: np.ndarray) -> np.ndarray:
        return np.clip(s + d, 0, 1)

    return base._blend(src, dst, blend)
