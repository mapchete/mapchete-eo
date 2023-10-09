import numpy as np
import pytest

from mapchete_eo import image_filters


def test_blur(test_3d_array):
    assert not np.array_equal(image_filters.blur(test_3d_array), test_3d_array)


def test_contour(test_3d_array):
    assert not np.array_equal(image_filters.contour(test_3d_array), test_3d_array)


def test_detail(test_3d_array):
    assert not np.array_equal(image_filters.detail(test_3d_array), test_3d_array)


def test_edge_enhance(test_3d_array):
    assert not np.array_equal(image_filters.edge_enhance(test_3d_array), test_3d_array)


def test_edge_enhance_more(test_3d_array):
    assert not np.array_equal(
        image_filters.edge_enhance_more(test_3d_array), test_3d_array
    )


def test_emboss(test_3d_array):
    assert not np.array_equal(image_filters.emboss(test_3d_array), test_3d_array)


def test_find_edges(test_3d_array):
    assert not np.array_equal(image_filters.find_edges(test_3d_array), test_3d_array)


def test_sharpen(test_3d_array):
    assert not np.array_equal(image_filters.sharpen(test_3d_array), test_3d_array)


def test_smooth(test_3d_array):
    assert not np.array_equal(image_filters.smooth(test_3d_array), test_3d_array)


def test_smooth_more(test_3d_array):
    assert not np.array_equal(image_filters.smooth_more(test_3d_array), test_3d_array)


def test_unsharp_mask(test_3d_array):
    assert not np.array_equal(image_filters.unsharp_mask(test_3d_array), test_3d_array)


def test_median(test_3d_array):
    assert not np.array_equal(image_filters.median(test_3d_array), test_3d_array)


def test_gaussian_blur(test_3d_array):
    assert not np.array_equal(image_filters.gaussian_blur(test_3d_array), test_3d_array)


def test_sharpen_16bit(test_3d_array):
    assert not np.array_equal(image_filters.sharpen_16bit(test_3d_array), test_3d_array)


def test_errors(test_3d_array):
    # data type error
    with pytest.raises(TypeError):
        image_filters.blur(test_3d_array.astype(np.uint16))

    # dimension error
    with pytest.raises(TypeError):
        image_filters.blur(test_3d_array[0])

    # shape error
    with pytest.raises(TypeError):
        image_filters.blur(np.stack([test_3d_array[0]]))
