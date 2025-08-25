import numpy as np
import numpy.ma as ma
import pytest

from mapchete_eo.image_operations import compositing, blend_functions

BLEND_FUNCS = [
    blend_functions.normal,
    blend_functions.multiply,
    blend_functions.screen,
    blend_functions.overlay,
    blend_functions.soft_light,
    blend_functions.hard_light,
    blend_functions.lighten_only,
    blend_functions.darken_only,
    blend_functions.dodge,
    blend_functions.addition,
    blend_functions.subtract,
    blend_functions.difference,
    blend_functions.divide,
    blend_functions.grain_extract,
    blend_functions.grain_merge,
]

# ---------------------------
# to_rgba tests
# ---------------------------


@pytest.mark.parametrize("bands", range(1, 5))
def test_to_rgba_shapes_and_types(test_2d_array, bands):
    # Repeat the 2D array to create 'bands' bands
    arr = np.repeat(np.expand_dims(test_2d_array, axis=0), bands, axis=0)
    out = compositing.to_rgba(arr)
    assert isinstance(out, np.ndarray)
    assert out.shape == (4, 256, 256)
    assert out.dtype == np.float16
    assert out.min() >= 0
    assert out.max() <= 255


def test_to_rgba_type_error(test_2d_array):
    # Should raise TypeError for non-uint8
    with pytest.raises(TypeError):
        compositing.to_rgba(test_2d_array.astype(np.uint16))


def test_to_rgba_invalid_band_counts():
    # More than 4 bands triggers TypeError
    data = np.random.randint(0, 255, (5, 2, 2), dtype=np.uint8)
    arr = ma.MaskedArray(data)
    with pytest.raises(TypeError):
        compositing.to_rgba(arr)
    # Zero bands also triggers TypeError
    data0 = np.empty((0, 2, 2), dtype=np.uint8)
    arr0 = ma.MaskedArray(data0)
    with pytest.raises(TypeError):
        compositing.to_rgba(arr0)


def test_to_rgba_expanded_mask_bool_scalar():
    # Create a 1-band masked array where mask is a scalar np.bool_
    data = np.ones((1, 2, 2), dtype=np.uint8)
    arr = ma.MaskedArray(data)
    arr.mask = np.bool_(True)  # triggers the np.bool_ branch in _expanded_mask

    out = compositing.to_rgba(arr)
    # Alpha should be zero everywhere because mask=True
    assert np.all(out[3] == 0)
    assert out.shape == (4, 2, 2)


def test_to_rgba_expanded_mask_bool_array():
    # 3-band masked array with all False mask
    data = np.ones((3, 2, 2), dtype=np.uint8) * 100
    arr = ma.MaskedArray(data, mask=False)
    out = compositing.to_rgba(arr)
    # Alpha should be 255 everywhere
    assert np.all(out[3] == 255)


def test_to_rgba_mixed_mask_values():
    # 3-band array with mixed masked/unmasked values
    data = np.array(
        [[[10, 20], [30, 40]], [[50, 60], [70, 80]], [[90, 100], [110, 120]]],
        dtype=np.uint8,
    )
    mask = np.array(
        [
            [[False, True], [False, True]],
            [[True, False], [True, False]],
            [[False, False], [True, True]],
        ]
    )
    arr = ma.MaskedArray(data, mask=mask)
    out = compositing.to_rgba(arr)
    assert out.shape == (4, 2, 2)
    # alpha channel should be 255 only where all bands are unmasked
    expected_alpha = np.zeros((2, 2), dtype=np.uint8)
    assert np.array_equal(out[3], expected_alpha)


def test_to_rgba_two_band_array():
    # 2-band array triggers the 2-band branch
    data = np.ones((2, 2, 2), dtype=np.uint8) * 100
    arr = ma.MaskedArray(data, mask=False)
    out = compositing.to_rgba(arr)
    assert out.shape == (4, 2, 2)
    # First 3 channels are copies of band0, 4th is band1
    assert np.all(out[0] == out[1])
    assert np.all(out[1] == out[2])
    assert np.all(out[3] == arr[1])


def test_to_rgba_four_band_array():
    # 4-band array triggers the 4-band branch
    data = np.ones((4, 2, 2), dtype=np.uint8) * 100
    arr = ma.MaskedArray(data, mask=False)
    out = compositing.to_rgba(arr)
    assert out.shape == (4, 2, 2)
    # Output should equal input data
    assert np.all(out == arr.data)


def test_to_rgba_expanded_mask_and_non_maskedarray():
    import numpy as np
    import numpy.ma as ma
    from mapchete_eo.image_operations import compositing

    # -------------------------------
    # Part 1: input is not a MaskedArray
    # -------------------------------
    data = np.array([[10, 20], [30, 40]], dtype=np.uint8)  # shape (2,2)

    # Pass a plain ndarray (not a MaskedArray)
    out = compositing.to_rgba(data[np.newaxis, ...])  # shape (1,2,2)
    assert isinstance(out, np.ndarray)
    assert out.shape == (4, 2, 2)
    # alpha channel should be 255 everywhere because no mask
    assert np.all(out[3] == 255)

    # -------------------------------
    # Part 2: MaskedArray with scalar boolean mask
    # -------------------------------
    arr_masked = ma.MaskedArray(data, mask=np.bool_(True)).reshape((1, 2, 2))
    out2 = compositing.to_rgba(arr_masked)
    assert isinstance(out2, np.ndarray)
    assert out2.shape == (4, 2, 2)
    # alpha channel should be 0 everywhere
    assert np.all(out2[3] == 0)

    # Scalar False case
    arr_masked_false = ma.MaskedArray(data, mask=np.bool_(False)).reshape((1, 2, 2))
    out3 = compositing.to_rgba(arr_masked_false)
    assert np.all(out3[3] == 255)


# ---------------------------
# _blend_base and composite
# ---------------------------


@pytest.mark.parametrize("blend_func", BLEND_FUNCS)
def test_blend_base_all_functions(test_3d_array, blend_func):
    bg = test_3d_array.astype(np.uint8)
    fg = test_3d_array.astype(np.uint8)
    out = compositing._blend_base(bg, fg, 0.5, blend_func)
    assert isinstance(out, ma.MaskedArray)
    assert out.shape == (4, bg.shape[1], bg.shape[2])
    assert out.dtype == np.uint8


@pytest.mark.parametrize("method", compositing.METHODS.keys())
def test_composite_dispatch(test_3d_array, method):
    out = compositing.composite(method, test_3d_array, test_3d_array)
    assert isinstance(out, ma.MaskedArray)
    assert out.shape == (4, 256, 256)


# ---------------------------
# fuzzy_mask tests
# ---------------------------


@pytest.mark.parametrize("bands", [1, 3])
@pytest.mark.parametrize("radius", [0, 3])
@pytest.mark.parametrize("invert", [True, False])
@pytest.mark.parametrize("dilate", [True, False])
def test_fuzzy_mask_shapes(test_2d_array, bands, radius, invert, dilate):
    arr = np.repeat(np.expand_dims(test_2d_array, axis=0), bands, axis=0)
    out = compositing.fuzzy_mask(
        arr, fill_value=10, radius=radius, invert=invert, dilate=dilate
    )
    assert isinstance(out, np.ndarray)
    assert out.shape == (256, 256)
    assert out.dtype == np.uint8


def test_fuzzy_mask_invalid_dimensions():
    arr = np.zeros((4, 256, 256), dtype=bool)
    with pytest.raises(TypeError):
        compositing.fuzzy_mask(arr, fill_value=255)


def test_fuzzy_mask_ndim_and_band_branches():
    # -----------------------
    # 2D input → triggers arr.ndim == 2 branch
    # -----------------------
    arr_2d = np.zeros((5, 5), dtype=bool)
    out_2d = compositing.fuzzy_mask(arr_2d, fill_value=10, invert=False, dilate=False)
    assert out_2d.shape == (5, 5)
    assert out_2d.dtype == np.uint8

    # -----------------------
    # 3D input with 1 band → triggers arr.shape[0] == 1 branch
    # -----------------------
    arr_3d_1band = np.zeros((1, 4, 4), dtype=bool)
    out_1band = compositing.fuzzy_mask(
        arr_3d_1band, fill_value=20, invert=False, dilate=False
    )
    assert out_1band.shape == (4, 4)
    assert out_1band.dtype == np.uint8

    # -----------------------
    # 3D input with 3 bands → triggers arr.shape[0] == 3 branch
    # -----------------------
    arr_3d_3band = np.zeros((3, 3, 3), dtype=bool)
    out_3band = compositing.fuzzy_mask(
        arr_3d_3band, fill_value=30, invert=False, dilate=False
    )
    assert out_3band.shape == (3, 3)
    assert out_3band.dtype == np.uint8

    # -----------------------
    # Invalid number of bands → triggers TypeError
    # -----------------------
    arr_invalid = np.zeros((2, 2, 2, 2), dtype=bool)
    with pytest.raises(TypeError, match="array must have exactly three dimensions"):
        compositing.fuzzy_mask(arr_invalid, fill_value=10)

    # -----------------------
    # Invalid single band number → triggers TypeError
    # -----------------------
    arr_invalid_bands = np.zeros((2, 4, 4), dtype=bool)  # 2 bands, not 1 or 3
    with pytest.raises(TypeError, match="array must have either one or three bands"):
        compositing.fuzzy_mask(arr_invalid_bands, fill_value=10)


# ---------------------------
# fuzzy_alpha_mask tests
# ---------------------------


@pytest.mark.parametrize("gradient_position", list(compositing.GradientPosition))
def test_fuzzy_alpha_mask_basic(test_3d_array, gradient_position):
    mask = np.ones((3, 256, 256), dtype=bool)
    out = compositing.fuzzy_alpha_mask(
        test_3d_array, mask=mask, radius=0, gradient_position=gradient_position
    )
    assert isinstance(out, np.ndarray)
    assert out.shape == (4, 256, 256)
    assert out.dtype == np.uint8


def test_fuzzy_alpha_mask_without_mask(test_3d_array):
    arr = ma.MaskedArray(test_3d_array, mask=False)
    out = compositing.fuzzy_alpha_mask(arr, radius=0)
    assert isinstance(out, np.ndarray)
    assert out.shape == (4, 256, 256)


def test_fuzzy_alpha_mask_invalid_input():
    arr = np.zeros((4, 256, 256), dtype=np.uint8)
    with pytest.raises(TypeError):
        compositing.fuzzy_alpha_mask(arr)


def test_fuzzy_alpha_mask_invalid_gradient_position(test_3d_array):
    mask = np.ones((3, 256, 256), dtype=bool)
    with pytest.raises(ValueError, match="unknown gradient_position"):
        compositing.fuzzy_alpha_mask(
            test_3d_array, mask=mask, gradient_position="invalid_position"
        )


def test_fuzzy_alpha_mask_mask_none_branch():
    # Case 1: arr is a MaskedArray → should use arr.mask
    data = np.random.randint(0, 255, (3, 4, 4), dtype=np.uint8)
    mask = np.array(
        [
            [
                [True, False, True, False],
                [False, True, False, True],
                [True, True, False, False],
                [False, False, True, True],
            ],
            [
                [False, False, True, True],
                [True, True, False, False],
                [False, True, True, False],
                [True, False, False, True],
            ],
            [
                [True, False, False, True],
                [False, True, True, False],
                [True, False, True, False],
                [False, True, False, True],
            ],
        ],
        dtype=bool,
    )
    arr = ma.MaskedArray(data, mask=mask)

    out = compositing.fuzzy_alpha_mask(arr, mask=None, radius=0, fill_value=10)
    assert out.shape == (4, 4, 4)  # 3 original bands + 1 alpha
    assert out.dtype == np.uint8

    # Case 2: arr is not a MaskedArray → should raise TypeError
    arr_np = np.random.randint(0, 255, (3, 4, 4), dtype=np.uint8)
    with pytest.raises(
        TypeError,
        match="input array must be a numpy MaskedArray or mask must be provided",
    ):
        compositing.fuzzy_alpha_mask(arr_np, mask=None)


# ---------------------------
# Ensure Timer branches are hit
# ---------------------------


def test_fuzzy_mask_timer_invoked(monkeypatch):
    def fake_timer():
        class T:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                return False

        return T()

    monkeypatch.setattr(compositing, "Timer", fake_timer)
    arr = np.zeros((1, 2, 2), dtype=bool)
    out = compositing.fuzzy_mask(arr, fill_value=1, radius=2)
    assert out.shape == (2, 2)
