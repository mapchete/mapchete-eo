import pytest
import numpy as np
import mapchete_eo.image_operations.blend_modes.blending_functions as bf
from mapchete_eo.image_operations.blend_modes.blending_functions import BlendBase


# List of blend modes (replace with actual blend function names)
blend_names = [
    "normal",
    "multiply",
    "screen",
    "overlay",
    "lighten_only",
    "darken_only",
    # add your modes here...
]

# Blend modes that allow opacity parameter
blend_modes_with_opacity = {
    "normal",
    "multiply",
    "screen",
    "overlay",
    # add other modes supporting opacity here
}

# Blend modes where result can equal dst_image at opacity=1.0 (no difference expected)
blend_modes_allowing_equal = {"lighten_only", "some_other_modes_if_any"}


def test_func_behavior_with_blendbase():
    base = BlendBase()

    def test_blend_func(s, d):
        return s  # just src, opacity applied outside in BlendBase.blend()

    src = np.ones((2, 2, 4), dtype=np.float16)
    dst = np.zeros((2, 2, 4), dtype=np.float16)

    def func(
        src: np.ndarray,
        dst: np.ndarray,
        opacity: float = 1.0,
        disable_type_checks: bool = False,
        dtype: np.dtype = np.float16,
    ) -> np.ndarray:
        if (
            opacity != base.opacity
            or disable_type_checks != base.disable_type_checks
            or dtype != base.dtype
        ):
            base_local = BlendBase(opacity, disable_type_checks, dtype)

            def local_blend_func(s, d):
                return s  # raw src only

            return base_local.blend(src, dst, local_blend_func)
        return base.blend(src, dst, test_blend_func)

    # opacity=1.0 => output == src
    result_default = func(src, dst)
    assert np.allclose(result_default, src)
    assert result_default.dtype == np.float16
    assert result_default.shape == src.shape

    # opacity=0.3 => output == 0.3*src + 0.7*dst = 0.3 * 1 + 0.7 * 0 = 0.3
    result_opacity = func(src, dst, opacity=0.3)
    expected = 0.3 * src + 0.7 * dst
    assert np.allclose(result_opacity, expected)
    assert result_opacity.dtype == np.float16
    assert result_opacity.shape == src.shape


def test_make_blend_function_default_path():
    # Create a dummy blend function, e.g. returns src
    def dummy_blend(s, d):
        return s

    func = bf.make_blend_function(dummy_blend)

    src = np.ones((2, 2, 4), dtype=np.float16)
    dst = np.zeros((2, 2, 4), dtype=np.float16)

    # Call with default params to hit the return base.blend() line
    result = func(src, dst)

    assert np.allclose(result, src)
    assert result.dtype == np.float16
    assert result.shape == src.shape


def test_prepare_type_checks_enabled_casting():
    blend = BlendBase()
    blend.disable_type_checks = False
    blend.fcn_name = "test_blend"
    blend.dtype = np.float16
    blend.opacity = 1.0

    # Valid 3D float64 arrays with 4 channels -> should cast to float16
    src = np.ones((2, 2, 4), dtype=np.float64)
    dst = np.zeros((2, 2, 4), dtype=np.float64)

    src_out, dst_out = blend._prepare(src, dst)

    assert src_out.dtype == np.float16
    assert dst_out.dtype == np.float16
    assert src_out.shape == src.shape
    assert dst_out.shape == dst.shape


def test_prepare_type_checks_enabled_no_cast():
    blend = BlendBase()
    blend.disable_type_checks = False
    blend.fcn_name = "test_blend"
    blend.dtype = np.float16
    blend.opacity = 1.0

    # Correct dtype and shape: no cast, outputs share memory
    src = np.ones((2, 2, 4), dtype=np.float16)
    dst = np.zeros((2, 2, 4), dtype=np.float16)

    src_out, dst_out = blend._prepare(src, dst)

    assert src_out.dtype == np.float16
    assert dst_out.dtype == np.float16
    assert np.shares_memory(src, src_out)
    assert np.shares_memory(dst, dst_out)


def test_prepare_type_checks_disabled_casting():
    blend = BlendBase()
    blend.disable_type_checks = True  # disables type and shape checks
    blend.fcn_name = "test_blend"
    blend.dtype = np.float16
    blend.opacity = 1.0

    # Invalid shape (2D), but no error because checks disabled; dtype cast applied
    src = np.ones((2, 2), dtype=np.float64)
    dst = np.zeros((2, 2), dtype=np.float64)

    src_out, dst_out = blend._prepare(src, dst)

    assert src_out.dtype == np.float16
    assert dst_out.dtype == np.float16
    assert src_out.shape == src.shape
    assert dst_out.shape == dst.shape


def test_prepare_type_checks_enabled_invalid_shape_raises():
    blend = BlendBase()
    blend.disable_type_checks = False
    blend.fcn_name = "test_blend"
    blend.dtype = np.float16
    blend.opacity = 1.0

    # Invalid 2D shape arrays; should raise TypeError due to assert_image_format
    src = np.ones((2, 2), dtype=np.float16)
    dst = np.zeros((2, 2), dtype=np.float16)

    with pytest.raises(TypeError, match="Expected: 3D array"):
        blend._prepare(src, dst)


def test_prepare_type_checks_enabled_invalid_channels_raises():
    blend = BlendBase()
    blend.disable_type_checks = False
    blend.fcn_name = "test_blend"
    blend.dtype = np.float16
    blend.opacity = 1.0

    # 3D shape but with 3 channels instead of 4, should raise on channel count
    src = np.ones((2, 2, 3), dtype=np.float16)
    dst = np.zeros((2, 2, 3), dtype=np.float16)

    with pytest.raises(TypeError, match="Expected: 4 layers"):
        blend._prepare(src, dst)


@pytest.mark.parametrize("blend_name", blend_names)
def test_blend_functions_opacity_zero(src_image, dst_images, blend_name):
    if blend_name not in dst_images:
        pytest.skip(f"No destination image for {blend_name}")

    if blend_name not in blend_modes_with_opacity:
        pytest.skip(f"Blend mode {blend_name} does not support opacity parameter")

    dst_image = dst_images[blend_name]
    blend_func = getattr(bf, blend_name)

    opacity = 0.0
    result = blend_func(
        src_image,
        dst_image,
        opacity=opacity,
        disable_type_checks=True,
        dtype=np.float16,
    )

    assert result.shape == src_image.shape
    assert result.dtype == np.float16, f"{blend_name} output dtype is not float16"
    assert (result >= 0).all() and (result <= 1).all()

    # Fully transparent blend: result should equal destination image
    np.testing.assert_allclose(result, dst_image.astype(np.float16), rtol=1e-3)


@pytest.mark.parametrize("blend_name", blend_names)
def test_blend_functions_opacity_one(src_image, dst_images, blend_name):
    if blend_name not in dst_images:
        pytest.skip(f"No destination image for {blend_name}")

    if blend_name not in blend_modes_with_opacity:
        pytest.skip(f"Blend mode {blend_name} does not support opacity parameter")

    dst_image = dst_images[blend_name]
    blend_func = getattr(bf, blend_name)

    opacity = 1.0
    result = blend_func(
        src_image,
        dst_image,
        opacity=opacity,
        disable_type_checks=True,
        dtype=np.float16,
    )

    assert result.shape == src_image.shape
    assert result.dtype == np.float16, f"{blend_name} output dtype is not float16"
    assert (result >= 0).all() and (result <= 1).all()

    # Only assert difference if blend mode expected to differ from dst_image at full opacity
    if blend_name not in blend_modes_allowing_equal:
        assert not np.allclose(
            result, dst_image.astype(np.float16)
        ), f"Blend mode {blend_name} with opacity=1.0 result equals dst_image, which is unexpected"


@pytest.mark.parametrize("blend_name", blend_names)
@pytest.mark.parametrize("opacity", [0.25, 0.5, 0.75])
def test_blend_functions_opacity_mid(src_image, dst_images, blend_name, opacity):
    if blend_name not in dst_images:
        pytest.skip(f"No destination image for {blend_name}")

    if blend_name not in blend_modes_with_opacity:
        pytest.skip(f"Blend mode {blend_name} does not support opacity parameter")

    dst_image = dst_images[blend_name]
    blend_func = getattr(bf, blend_name)

    result = blend_func(
        src_image,
        dst_image,
        opacity=opacity,
        disable_type_checks=True,
        dtype=np.float16,
    )

    assert result.shape == src_image.shape
    assert result.dtype == np.float16, f"{blend_name} output dtype is not float16"
    assert (result >= 0).all() and (result <= 1).all()


def test_burn_blend_basic():
    s = np.array([[0.5, 1.0], [0.2, 0.0]], dtype=np.float32)
    d = np.array([[0.2, 0.3], [0.9, 0.5]], dtype=np.float32)
    result = bf.burn_blend(s, d)

    # output shape and dtype checks
    assert result.shape == s.shape
    assert result.dtype == s.dtype

    # output range check
    assert (result >= 0).all() and (result <= 1).all()

    # no NaNs or Infs in output
    assert np.isfinite(result).all()

    # Check known values manually:
    # When s=0.5, d=0.2 => 1 - (1 - 0.2)/0.5 = 1 - 0.8/0.5 = 1 - 1.6 = -0.6 clipped to 0
    assert result[0, 0] == 0

    # When s=1.0, d=0.3 => 1 - (1 - 0.3)/1.0 = 1 - 0.7 = 0.3
    assert np.isclose(result[0, 1], 0.3)

    # When s=0 (division by zero), output should be 0, no NaNs
    assert result[1, 1] == 0


def test_burn_blend_all_ones():
    s = np.ones((3, 3), dtype=np.float32)
    d = np.ones((3, 3), dtype=np.float32)
    result = bf.burn_blend(s, d)
    # burn_blend(1,1) == 1 - (1-1)/1 = 1
    assert np.allclose(result, 1)


def test_burn_blend_zero_s_and_d():
    s = np.zeros((2, 2), dtype=np.float32)
    d = np.zeros((2, 2), dtype=np.float32)
    result = bf.burn_blend(s, d)
    # division by zero case, all values set to 0 safely
    assert np.all(result == 0)
