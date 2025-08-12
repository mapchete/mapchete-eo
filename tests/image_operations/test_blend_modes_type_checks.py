import numpy as np
import pytest

from mapchete_eo.image_operations.blend_modes.type_checks import (
    assert_image_format,
    assert_opacity,
)  # replace with actual module name


def test_valid_image_with_alpha():
    img = np.zeros((10, 10, 4), dtype=float)
    assert_image_format(img, "blend_func", "image")  # Should not raise


def test_valid_image_without_alpha_when_not_forced():
    img = np.zeros((10, 10, 3), dtype=float)
    assert_image_format(
        img, "blend_func", "image", force_alpha=False
    )  # Should not raise


def test_image_not_numpy_array():
    with pytest.raises(TypeError, match=r"\[Invalid Type\]"):
        assert_image_format("not an array", "blend_func", "image")


def test_image_wrong_dtype():
    img = np.zeros((10, 10, 4), dtype=np.uint8)
    with pytest.raises(TypeError, match=r"\[Invalid Data Type\]"):
        assert_image_format(img, "blend_func", "image")


def test_image_wrong_dimensions():
    img = np.zeros((10, 10), dtype=float)  # 2D
    with pytest.raises(TypeError, match=r"\[Invalid Dimensions\]"):
        assert_image_format(img, "blend_func", "image")


def test_image_wrong_channel_count_with_force_alpha():
    img = np.zeros((10, 10, 3), dtype=float)  # No alpha channel
    with pytest.raises(TypeError, match=r"\[Invalid Channel Count\]"):
        assert_image_format(img, "blend_func", "image", force_alpha=True)


def test_valid_opacity_float():
    assert_opacity(0.5, "blend_func")  # Should not raise


def test_valid_opacity_int():
    assert_opacity(1, "blend_func")  # Should not raise


def test_opacity_wrong_type():
    with pytest.raises(TypeError, match=r"\[Invalid Type\]"):
        assert_opacity("not a number", "blend_func")


def test_opacity_below_range():
    with pytest.raises(ValueError, match=r"\[Out of Range\]"):
        assert_opacity(-0.1, "blend_func")


def test_opacity_above_range():
    with pytest.raises(ValueError, match=r"\[Out of Range\]"):
        assert_opacity(1.1, "blend_func")
