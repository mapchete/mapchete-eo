import numpy as np
import numpy.ma as ma
import pytest

from mapchete_eo.image_operations import blend_functions, compositing


@pytest.mark.parametrize("bands", range(1, 5))
def test_to_rgba(bands, test_2d_array):
    arr = np.repeat(np.expand_dims(test_2d_array, axis=0), bands, axis=0)
    out = compositing.to_rgba(arr)
    assert isinstance(out, np.ndarray)
    assert not isinstance(out, ma.masked_array)
    assert out.shape == (4, 256, 256)
    assert out.dtype == np.float16
    assert out.min() >= 0.0
    assert out.max() <= 255.0


def test_to_rgba_dtype_error(test_2d_array):
    with pytest.raises(TypeError):
        compositing.to_rgba(test_2d_array.astype(np.uint16))


@pytest.mark.parametrize("method", compositing.METHODS.keys())
@pytest.mark.parametrize("opacity", [0, 0.5, 1])
def test_compositing_output_array(test_3d_array, method, opacity):
    out = compositing.composite(method, test_3d_array, test_3d_array, opacity=opacity)
    assert isinstance(out, ma.masked_array)
    assert out.shape == (4, 256, 256)
    assert out.dtype == np.uint8


@pytest.mark.parametrize("bands", [1, 3])
@pytest.mark.parametrize("radius", [0, 5])
@pytest.mark.parametrize("invert", [True, False])
@pytest.mark.parametrize("dilate", [True, False])
def test_fuzzy_mask(test_2d_array, bands, radius, invert, dilate):
    arr = np.repeat(np.expand_dims(test_2d_array, axis=0), bands, axis=0)
    out = compositing.fuzzy_mask(
        arr, fill_value=0, radius=radius, invert=invert, dilate=dilate
    )
    assert isinstance(out, np.ndarray)
    assert out.shape == (256, 256)
    assert out.dtype == np.uint8
    assert not np.array_equal(arr, out)


@pytest.mark.parametrize("mask", [np.ones((3, 256, 256), dtype=bool), None])
@pytest.mark.parametrize("radius", [0, 5])
@pytest.mark.parametrize("gradient_position", list(compositing.GradientPosition))
def test_fuzzy_alpha_mask(test_3d_array, mask, radius, gradient_position):
    out = compositing.fuzzy_alpha_mask(
        test_3d_array, mask=mask, radius=radius, gradient_position=gradient_position
    )
    assert isinstance(out, np.ndarray)
    assert out.shape == (4, 256, 256)
    assert out.dtype == np.uint8
    assert not np.array_equal(test_3d_array, out)


def test_fuzzy_alpha_mask_shape_error(test_3d_array):
    with pytest.raises(TypeError):
        compositing.fuzzy_alpha_mask(test_3d_array[0])


def test_fuzzy_alpha_mask_error(test_3d_array):
    with pytest.raises(TypeError):
        compositing.fuzzy_alpha_mask(test_3d_array.data)


def test_fuzzy_mask_with_arr_types_and_errors(test_2d_array, test_3d_array):
    """
    Test fuzzy_mask using pytest fixtures:
    - 2D input expands to 3D
    - 1-band 3D input stacks to 3 bands (subset of test_3d_array)
    - 3-band input used directly
    - invalid number of bands triggers TypeError
    - input with wrong ndim triggers TypeError
    """

    # 2D input (test_2d_array)
    out = compositing.fuzzy_mask(test_2d_array, fill_value=255)
    assert out.shape == test_2d_array.shape
    assert out.dtype == "uint8"

    # 1-band 3D input -> stack to 3 bands, use first band of test_3d_array
    test_1_band = test_3d_array[0]  # shape (1, H, W)
    out = compositing.fuzzy_mask(test_1_band, fill_value=255)
    assert out.shape == test_2d_array.shape
    assert out.dtype == "uint8"

    # 3-band input (test_3d_array)
    out = compositing.fuzzy_mask(test_3d_array, fill_value=255)
    assert out.shape == test_2d_array.shape
    assert out.dtype == "uint8"

    # invalid number of bands -> should raise TypeError
    arr_invalid = test_3d_array[0:2]  # 2 bands
    with pytest.raises(TypeError, match="array must have either one or three bands"):
        compositing.fuzzy_mask(arr_invalid, fill_value=255)

    # input with wrong ndim -> e.g., 1D array
    arr_1d = np.array([True, False, True])
    with pytest.raises(TypeError, match="array must have exactly three dimensions"):
        compositing.fuzzy_mask(arr_1d, fill_value=255)


@pytest.mark.parametrize("dtype", ["float16", "float32", np.float64])
def test_blend_base_real_dtype_conversion(test_3d_array, dtype):
    """
    Test _blend_base with real blend_functions operations and different compute_dtype values.
    Ensures string dtype is converted to np.dtype correctly.
    """
    bg = test_3d_array.astype(np.uint8)
    fg = test_3d_array.astype(np.uint8)
    opacity = 0.5

    # Use a real operation from blend_functions, e.g., normal
    out = compositing._blend_base(
        bg, fg, opacity, blend_functions.normal, compute_dtype=dtype
    )

    # Output checks
    assert isinstance(out, ma.MaskedArray)
    assert out.shape == (4, bg.shape[1], bg.shape[2])  # RGBA
    assert out.dtype == np.uint8
    assert out.min() >= 0
    assert out.max() <= 255


@pytest.mark.parametrize("dtype", ["float16", "float32"])
def test_blend_base_string_vs_numpy_dtype(test_3d_array, dtype):
    """
    Ensure _blend_base gives the same result for string dtype vs np.dtype.
    """
    bg = test_3d_array.astype(np.uint8)
    fg = test_3d_array.astype(np.uint8)
    opacity = 0.5

    out_str = compositing._blend_base(
        bg, fg, opacity, blend_functions.normal, compute_dtype=dtype
    )
    out_np = compositing._blend_base(
        bg, fg, opacity, blend_functions.normal, compute_dtype=np.dtype(dtype)
    )

    # Output checks
    assert isinstance(out_str, ma.MaskedArray)
    assert out_str.shape == (4, bg.shape[1], bg.shape[2])
    assert out_np.shape == (4, bg.shape[1], bg.shape[2])

    # Results should be identical
    assert np.array_equal(out_str.data, out_np.data)
    assert np.array_equal(out_str.mask, out_np.mask)


@pytest.mark.parametrize("mask_value", [True, False])
def test_to_rgba_expanded_mask(test_3d_array, mask_value):
    """
    Test to_rgba with _expanded_mask logic:
    - Uses test_3d_array (3 bands)
    - Covers single boolean mask and array mask
    """
    # If mask_value is a boolean, apply it to all elements
    if isinstance(mask_value, bool):
        arr = ma.MaskedArray(data=test_3d_array.data, mask=mask_value)
    else:
        arr = test_3d_array

    out = compositing.to_rgba(arr, compute_dtype=np.float16)

    # Output type and shape
    assert isinstance(out, np.ndarray)
    assert out.shape == (4, test_3d_array.shape[1], test_3d_array.shape[2])
    assert out.dtype == np.float16

    # Check alpha channel
    alpha = out[3]
    if mask_value is True:
        # Fully masked -> alpha = 0
        assert np.all(alpha == 0)
    elif mask_value is False:
        # No mask -> alpha = 255
        assert np.all(alpha == 255)
    else:
        # Original mask array -> alpha should be 255 where not masked, 0 where masked
        original_mask = np.any(arr.mask[:3], axis=0)
        expected_alpha = np.where(~original_mask, 255, 0)
        assert np.array_equal(alpha, expected_alpha)


def test_to_rgba_wraps_unmasked_array(test_3d_array):
    """
    Test that to_rgba wraps a regular ndarray into a MaskedArray
    with a default mask of all False.
    """
    # Use raw data (ndarray), not a masked array
    arr = test_3d_array.data  # shape: (3, 256, 256), dtype=uint8

    # Call to_rgba
    out = compositing.to_rgba(arr, compute_dtype=np.float16)

    # Output checks
    assert isinstance(out, np.ndarray)
    assert out.shape == (4, arr.shape[1], arr.shape[2])  # RGBA
    assert out.dtype == np.float16

    # Alpha channel should be fully opaque because original array had no mask
    alpha = out[3]
    assert np.all(alpha == 255)


def test_expanded_mask_simple():
    """
    Simple test for the _expanded_mask logic where the mask is a single boolean.
    """
    # Create a 1-band array
    data = np.array([[10, 20], [30, 40]], dtype=np.uint8)
    arr = ma.MaskedArray(np.expand_dims(data, axis=0))

    # Force the mask to a single boolean
    arr[0].mask = np.bool_(True)

    # Call to_rgba, which internally calls _expanded_mask
    out = compositing.to_rgba(arr)

    # Check that output is the correct shape and type
    assert isinstance(out, np.ndarray)
    assert out.shape == (4, 2, 2)  # 4 bands (RGBA)


def test_to_rgba_invalid_number_of_bands():
    """
    Test that to_rgba raises a TypeError when input has invalid number of bands (>4)
    """
    # Create an array with 5 bands (invalid)
    data = np.random.randint(0, 255, size=(5, 2, 2), dtype=np.uint8)
    arr = ma.MaskedArray(data)

    with pytest.raises(
        TypeError, match="array must have between 1 and 4 bands but has 5"
    ):
        compositing.to_rgba(arr)


def test_to_rgba_zero_bands():
    """
    Test that to_rgba raises a TypeError when input has 0 bands
    """
    data = np.empty((0, 2, 2), dtype=np.uint8)
    arr = ma.MaskedArray(data)

    with pytest.raises(
        TypeError, match="array must have between 1 and 4 bands but has 0"
    ):
        compositing.to_rgba(arr)
