import numpy as np
import numpy.ma as ma
import pytest

from mapchete_eo.image_operations import compositing


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
