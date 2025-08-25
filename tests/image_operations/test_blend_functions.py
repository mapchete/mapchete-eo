import numpy as np
import pytest
from mapchete_eo.image_operations import blend_functions as bf

blend_funcs = [
    bf.normal,
    bf.multiply,
    bf.screen,
    bf.overlay,
    bf.soft_light,
    bf.hard_light,
    bf.lighten_only,
    bf.darken_only,
    bf.dodge,
    bf.addition,
    bf.subtract,
    bf.difference,
    bf.divide,
    bf.grain_extract,
    bf.grain_merge,
]


# --- Test shapes and dtypes including compute_dtype ---
@pytest.mark.parametrize("func", blend_funcs)
@pytest.mark.parametrize(
    "compute_dtype", [np.float16, np.float32, np.float64, "float16", "float32"]
)
def test_blend_shapes_and_dtype(bg_array, fg_array, opacities, func, compute_dtype):
    """Verify output shape and dtype respects compute_dtype for multiple opacities"""
    for opacity in opacities:
        result = func(bg_array, fg_array, opacity, compute_dtype=compute_dtype)
        # Ensure it's a numpy array
        assert isinstance(result, np.ndarray)
        # Shape should match input
        assert result.shape == bg_array.shape
        # Convert string dtype to np.dtype if needed
        expected_dtype = (
            np.dtype(compute_dtype) if isinstance(compute_dtype, str) else compute_dtype
        )
        assert result.dtype == expected_dtype


# --- Control array test with compute_dtype ---
@pytest.mark.parametrize("opacity", [0.0, 0.5, 1.0])
@pytest.mark.parametrize(
    "compute_dtype", [np.float16, np.float32, np.float64, "float16", "float32"]
)
def test_normal_control_array_with_dtype(opacity, compute_dtype):
    bg = np.array([[0, 128]], dtype=np.float16)
    fg = np.array([[255, 128]], dtype=np.float16)
    result = bf.normal(bg, fg, opacity, compute_dtype=compute_dtype)
    expected = fg * opacity + bg * (1 - opacity)
    expected_dtype = (
        np.dtype(compute_dtype) if isinstance(compute_dtype, str) else compute_dtype
    )
    assert result.dtype == expected_dtype
    np.testing.assert_allclose(result, expected, rtol=1e-5)


@pytest.mark.parametrize("opacity", [0.0, 0.5, 1.0])
@pytest.mark.parametrize(
    "compute_dtype", [np.float16, np.float32, np.float64, "float16", "float32"]
)
def test_multiply_control_array_with_dtype(opacity, compute_dtype):
    """Multiply blend with known values at multiple opacities and compute_dtype"""
    bg = np.array([[100, 200]], dtype=np.float16)
    fg = np.array([[50, 50]], dtype=np.float16)

    # run the blend function
    result = bf.multiply(bg, fg, opacity, compute_dtype=compute_dtype)

    # determine the actual dtype to use for computing expected
    dtype = np.dtype(compute_dtype) if isinstance(compute_dtype, str) else compute_dtype
    bg_cast = bg.astype(dtype)
    fg_cast = fg.astype(dtype)

    # compute expected using the same dtype as compute_dtype
    expected = (bg_cast * fg_cast / 255) * opacity + bg_cast * (1 - opacity)

    # compare using float64 to avoid tiny precision issues
    np.testing.assert_allclose(
        result.astype(np.float64), expected.astype(np.float64), rtol=1e-5, atol=1e-3
    )

    # check that output dtype matches compute_dtype
    assert result.dtype == dtype


@pytest.mark.parametrize("opacity", [0.0, 0.5, 1.0])
@pytest.mark.parametrize(
    "compute_dtype", [np.float16, np.float32, np.float64, "float16", "float32"]
)
def test_divide_control_array_with_dtype(opacity, compute_dtype):
    """Divide blend handles fg=0 safely and respects opacity and dtype"""
    bg = np.array([[50, 200]], dtype=np.float16)
    fg = np.array([[0, 50]], dtype=np.float16)
    result = bf.divide(bg, fg, opacity, compute_dtype=compute_dtype)

    # compute expected values considering divide and opacity
    expected = np.empty_like(
        result,
        dtype=np.dtype(compute_dtype)
        if isinstance(compute_dtype, str)
        else compute_dtype,
    )
    # first element fg=0 triggers 255, blended with opacity
    expected[0, 0] = 255 * opacity + bg[0, 0] * (1 - opacity)
    # second element normal divide
    expected[0, 1] = min(255, (bg[0, 1] * 255 / fg[0, 1])) * opacity + bg[0, 1] * (
        1 - opacity
    )

    # check dtype
    expected_dtype = (
        np.dtype(compute_dtype) if isinstance(compute_dtype, str) else compute_dtype
    )
    assert result.dtype == expected_dtype
    # check values
    np.testing.assert_allclose(result, expected, rtol=1e-5)
