"""
Blending functions adapted from https://github.com/flrs/blend_modes
with alpha support, arbitrary image scale handling, and dtype control.
"""

import numpy as np
from typing import Callable, Optional
from mapchete_eo.image_operations.blend_modes.type_checks import (
    assert_image_format,
    assert_opacity,
)


def _compose_alpha(img_in: np.ndarray, img_layer: np.ndarray, opacity: float):
    """Calculate alpha composition ratio between two RGBA images."""
    comp_alpha = np.minimum(img_in[:, :, 3], img_layer[:, :, 3]) * opacity
    new_alpha = img_in[:, :, 3] + (1.0 - img_in[:, :, 3]) * comp_alpha
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = comp_alpha / new_alpha
    ratio[np.isnan(ratio)] = 0.0
    return ratio, new_alpha


class BlendBase:
    def __init__(
        self,
        opacity: float = 1.0,
        disable_type_checks: bool = False,
        fcn_name: str = "BlendBase",
        input_dtype: Optional[None] = None,
        output_dtype: Optional[None] = None,
    ):
        self.opacity = opacity
        self.disable_type_checks = disable_type_checks
        self.fcn_name = fcn_name
        self.input_dtype = input_dtype
        self.output_dtype = output_dtype

    def _prepare(self, src: np.ndarray, dst: np.ndarray):
        # Type checks
        if not self.disable_type_checks:
            assert_image_format(src, fcn_name=self.fcn_name, arg_name="src")
            assert_image_format(dst, fcn_name=self.fcn_name, arg_name="dst")
            assert_opacity(self.opacity, fcn_name=self.fcn_name)

        # Convert input dtype if requested
        if self.input_dtype is not None:
            src = src.astype(self.input_dtype, copy=False)
            dst = dst.astype(self.input_dtype, copy=False)
        else:
            src = src.astype(np.float16, copy=False)
            dst = dst.astype(np.float16, copy=False)

        # Determine scale for rescaling later
        scale = max(np.max(src), np.max(dst), 1.0)
        src /= scale
        dst /= scale

        # Ensure RGBA
        if src.shape[2] == 3:
            src = np.concatenate(
                [src, np.ones((*src.shape[:2], 1), dtype=src.dtype)], axis=2
            )
        if dst.shape[2] == 3:
            dst = np.concatenate(
                [dst, np.ones((*dst.shape[:2], 1), dtype=dst.dtype)], axis=2
            )

        return src, dst, scale

    def blend(self, src: np.ndarray, dst: np.ndarray, blend_func: Callable):
        src, dst, scale = self._prepare(src, dst)

        # Blend RGB channels
        blended_rgb = blend_func(src[:, :, :3], dst[:, :, :3])

        # Compose alpha
        ratio, new_alpha = _compose_alpha(dst, src, self.opacity)

        # Combine with alpha ratio
        out_rgb = (blended_rgb * ratio[:, :, None]) + (
            dst[:, :, :3] * (1 - ratio[:, :, None])
        )

        # Combine final result
        result = np.concatenate([out_rgb, new_alpha[:, :, None]], axis=2)
        result = np.clip(result, 0, 1)

        # Rescale to original range
        result *= scale

        # Convert output dtype if requested
        if self.output_dtype is not None:
            result = result.astype(self.output_dtype)
        return result


def make_blend_function(blend_func: Callable):
    base = BlendBase()

    def func(
        src: np.ndarray,
        dst: np.ndarray,
        opacity: float = 1.0,
        disable_type_checks: bool = False,
        dtype=None,  # old param for backward compatibility
        input_dtype=None,
        output_dtype=None,
    ):
        # If dtype is given, map to output_dtype
        if dtype is not None:
            output_dtype = dtype

        if (
            opacity != base.opacity
            or disable_type_checks != base.disable_type_checks
            or input_dtype != base.input_dtype
            or output_dtype != base.output_dtype
        ):
            base_local = BlendBase(
                opacity,
                disable_type_checks,
                input_dtype=input_dtype,
                output_dtype=output_dtype,
            )
            return base_local.blend(src, dst, blend_func)

        return base.blend(src, dst, blend_func)

    return func


# -----------------------------
# Core blending functions
# -----------------------------
normal = make_blend_function(lambda s, d: s)
multiply = make_blend_function(lambda s, d: s * d)
screen = make_blend_function(lambda s, d: 1 - (1 - s) * (1 - d))
darken_only = make_blend_function(lambda s, d: np.minimum(s, d))
lighten_only = make_blend_function(lambda s, d: np.maximum(s, d))
difference = make_blend_function(lambda s, d: np.abs(d - s))
subtract = make_blend_function(lambda s, d: np.clip(d - s, 0, 1))
addition = make_blend_function(lambda s, d: np.clip(s + d, 0, 1))


def divide_blend(s: np.ndarray, d: np.ndarray):
    with np.errstate(divide="ignore", invalid="ignore"):
        res = np.true_divide(d, s)
        res[~np.isfinite(res)] = 0
    return np.clip(res, 0, 1)


divide = make_blend_function(divide_blend)


def grain_extract_blend(s: np.ndarray, d: np.ndarray):
    return np.clip(d - s + 0.5, 0, 1)


grain_extract = make_blend_function(grain_extract_blend)


def grain_merge_blend(s: np.ndarray, d: np.ndarray):
    return np.clip(d + s - 0.5, 0, 1)


grain_merge = make_blend_function(grain_merge_blend)


def overlay_blend(s: np.ndarray, d: np.ndarray):
    mask = d <= 0.5
    result = np.empty_like(d)
    result[mask] = 2 * s[mask] * d[mask]
    result[~mask] = 1 - 2 * (1 - s[~mask]) * (1 - d[~mask])
    return np.clip(result, 0, 1)


overlay = make_blend_function(overlay_blend)


def hard_light_blend(s: np.ndarray, d: np.ndarray):
    mask = s <= 0.5
    result = np.empty_like(d)
    result[mask] = 2 * s[mask] * d[mask]
    result[~mask] = 1 - 2 * (1 - s[~mask]) * (1 - d[~mask])
    return np.clip(result, 0, 1)


hard_light = make_blend_function(hard_light_blend)


def soft_light_blend(s: np.ndarray, d: np.ndarray):
    result = (1 - 2 * s) * d**2 + 2 * s * d
    return np.clip(result, 0, 1)


soft_light = make_blend_function(soft_light_blend)


def dodge_blend(s: np.ndarray, d: np.ndarray):
    with np.errstate(divide="ignore", invalid="ignore"):
        res = np.true_divide(d, 1 - s)
        res[~np.isfinite(res)] = 1
    return np.clip(res, 0, 1)


dodge = make_blend_function(dodge_blend)


def burn_blend(s: np.ndarray, d: np.ndarray):
    with np.errstate(divide="ignore", invalid="ignore"):
        res = 1 - np.true_divide(1 - d, s)
        res[~np.isfinite(res)] = 0
    return np.clip(res, 0, 1)


burn = make_blend_function(burn_blend)
