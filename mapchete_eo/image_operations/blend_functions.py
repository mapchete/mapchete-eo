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

"""

import numpy as np


def normal(
    bg: np.ndarray, fg: np.ndarray, opacity: float = 1.0, compute_dtype=np.float16
) -> np.ndarray:
    bg = bg.astype(compute_dtype)
    fg = fg.astype(compute_dtype)
    return fg * opacity + bg * (1 - opacity)


def multiply(
    bg: np.ndarray, fg: np.ndarray, opacity: float = 1.0, compute_dtype=np.float16
) -> np.ndarray:
    bg = bg.astype(compute_dtype)
    fg = fg.astype(compute_dtype)
    return (bg * fg / 255) * opacity + bg * (1 - opacity)


def screen(
    bg: np.ndarray, fg: np.ndarray, opacity: float = 1.0, compute_dtype=np.float16
) -> np.ndarray:
    bg = bg.astype(compute_dtype)
    fg = fg.astype(compute_dtype)
    return (255 - ((255 - bg) * (255 - fg) / 255)) * opacity + bg * (1 - opacity)


def overlay(
    bg: np.ndarray, fg: np.ndarray, opacity: float = 1.0, compute_dtype=np.float16
) -> np.ndarray:
    bg = bg.astype(compute_dtype)
    fg = fg.astype(compute_dtype)
    mask = bg < 128
    out = np.zeros_like(bg, dtype=compute_dtype)
    out[mask] = 2 * bg[mask] * fg[mask] / 255
    out[~mask] = 255 - 2 * (255 - bg[~mask]) * (255 - fg[~mask]) / 255
    return out * opacity + bg * (1 - opacity)


def soft_light(
    bg: np.ndarray, fg: np.ndarray, opacity: float = 1.0, compute_dtype=np.float16
) -> np.ndarray:
    bg = bg.astype(compute_dtype) / 255
    fg = fg.astype(compute_dtype) / 255
    out = (1 - 2 * fg) * bg**2 + 2 * fg * bg
    return np.clip(out * 255 * opacity + bg * 255 * (1 - opacity), 0, 255).astype(
        compute_dtype
    )


def hard_light(
    bg: np.ndarray, fg: np.ndarray, opacity: float = 1.0, compute_dtype=np.float16
) -> np.ndarray:
    bg = bg.astype(compute_dtype)
    fg = fg.astype(compute_dtype)
    mask = fg < 128
    out = np.zeros_like(bg, dtype=compute_dtype)
    out[mask] = 2 * fg[mask] * bg[mask] / 255
    out[~mask] = 255 - 2 * (255 - fg[~mask]) * (255 - bg[~mask]) / 255
    return out * opacity + bg * (1 - opacity)


def lighten_only(
    bg: np.ndarray, fg: np.ndarray, opacity: float = 1.0, compute_dtype=np.float16
) -> np.ndarray:
    bg = bg.astype(compute_dtype)
    fg = fg.astype(compute_dtype)
    return np.maximum(bg, fg) * opacity + bg * (1 - opacity)


def darken_only(
    bg: np.ndarray, fg: np.ndarray, opacity: float = 1.0, compute_dtype=np.float16
) -> np.ndarray:
    bg = bg.astype(compute_dtype)
    fg = fg.astype(compute_dtype)
    return np.minimum(bg, fg) * opacity + bg * (1 - opacity)


def dodge(
    bg: np.ndarray, fg: np.ndarray, opacity: float = 1.0, compute_dtype=np.float16
) -> np.ndarray:
    bg = bg.astype(compute_dtype)
    fg = fg.astype(compute_dtype)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(fg == 255, 255, np.minimum(255, bg * 255 / (255 - fg)))
    return out * opacity + bg * (1 - opacity)


def addition(
    bg: np.ndarray, fg: np.ndarray, opacity: float = 1.0, compute_dtype=np.float16
) -> np.ndarray:
    bg = bg.astype(compute_dtype)
    fg = fg.astype(compute_dtype)
    return np.clip(bg + fg, 0, 255) * opacity + bg * (1 - opacity)


def subtract(
    bg: np.ndarray, fg: np.ndarray, opacity: float = 1.0, compute_dtype=np.float16
) -> np.ndarray:
    bg = bg.astype(compute_dtype)
    fg = fg.astype(compute_dtype)
    return np.clip(bg - fg, 0, 255) * opacity + bg * (1 - opacity)


def difference(
    bg: np.ndarray, fg: np.ndarray, opacity: float = 1.0, compute_dtype=np.float16
) -> np.ndarray:
    bg = bg.astype(compute_dtype)
    fg = fg.astype(compute_dtype)
    return np.abs(bg - fg) * opacity + bg * (1 - opacity)


def divide(
    bg: np.ndarray, fg: np.ndarray, opacity: float = 1.0, compute_dtype=np.float16
) -> np.ndarray:
    bg = bg.astype(compute_dtype)
    fg = fg.astype(compute_dtype)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(fg == 0, 255, np.clip(bg * 255 / fg, 0, 255))
    return out * opacity + bg * (1 - opacity)


def grain_extract(
    bg: np.ndarray, fg: np.ndarray, opacity: float = 1.0, compute_dtype=np.float16
) -> np.ndarray:
    bg = bg.astype(compute_dtype)
    fg = fg.astype(compute_dtype)
    return np.clip(bg - fg + 128, 0, 255) * opacity + bg * (1 - opacity)


def grain_merge(
    bg: np.ndarray, fg: np.ndarray, opacity: float = 1.0, compute_dtype=np.float16
) -> np.ndarray:
    bg = bg.astype(compute_dtype)
    fg = fg.astype(compute_dtype)
    return np.clip(bg + fg - 128, 0, 255) * opacity + bg * (1 - opacity)
