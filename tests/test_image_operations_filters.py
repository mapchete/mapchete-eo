import numpy as np
import pytest

from mapchete_eo.image_operations import filters


def test_blur(test_3d_array):
    assert not np.array_equal(filters.blur(test_3d_array), test_3d_array)


def test_contour(test_3d_array):
    assert not np.array_equal(filters.contour(test_3d_array), test_3d_array)


def test_detail(test_3d_array):
    assert not np.array_equal(filters.detail(test_3d_array), test_3d_array)


def test_edge_enhance(test_3d_array):
    assert not np.array_equal(filters.edge_enhance(test_3d_array), test_3d_array)


def test_edge_enhance_more(test_3d_array):
    assert not np.array_equal(filters.edge_enhance_more(test_3d_array), test_3d_array)


def test_emboss(test_3d_array):
    assert not np.array_equal(filters.emboss(test_3d_array), test_3d_array)


def test_find_edges(test_3d_array):
    assert not np.array_equal(filters.find_edges(test_3d_array), test_3d_array)


def test_sharpen(test_3d_array):
    assert not np.array_equal(filters.sharpen(test_3d_array), test_3d_array)


def test_smooth(test_3d_array):
    assert not np.array_equal(filters.smooth(test_3d_array), test_3d_array)


def test_smooth_more(test_3d_array):
    assert not np.array_equal(filters.smooth_more(test_3d_array), test_3d_array)


def test_unsharp_mask(test_3d_array):
    assert not np.array_equal(filters.unsharp_mask(test_3d_array), test_3d_array)


def test_median(test_3d_array):
    assert not np.array_equal(filters.median(test_3d_array), test_3d_array)


def test_gaussian_blur(test_3d_array):
    assert not np.array_equal(filters.gaussian_blur(test_3d_array), test_3d_array)


def test_sharpen_16bit(test_3d_array):
    assert not np.array_equal(filters.sharpen_16bit(test_3d_array), test_3d_array)


def test_errors(test_3d_array):
    # data type error
    with pytest.raises(TypeError):
        filters.blur(test_3d_array.astype(np.uint16))

    # dimension error
    with pytest.raises(TypeError):
        filters.blur(test_3d_array[0])

    # shape error
    with pytest.raises(TypeError):
        filters.blur(np.stack([test_3d_array[0]]))
