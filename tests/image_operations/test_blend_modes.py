import pytest
import numpy as np
import mapchete_eo.image_operations.blend_modes.blending_functions as bf
from mapchete_eo.image_operations.blend_modes.blending_functions import BlendBase

# List of blend modes
blend_names = [
    "normal",
    "multiply",
    "screen",
    "overlay",
    "lighten_only",
    "darken_only",
]

# Blend modes that allow opacity
blend_modes_with_opacity = {"normal", "multiply", "screen", "overlay"}

# Blend modes that may equal dst_image at opacity=1.0
blend_modes_allowing_equal = {"lighten_only"}


def test_func_behavior_with_blendbase():
    base = BlendBase(
        disable_type_checks=True
    )  # Disable type checks for 3-channel input

    src = np.ones((2, 2, 3), dtype=np.float16)
    dst = np.zeros((2, 2, 3), dtype=np.float16)

    # Default opacity=1.0, output should match src (scaled)
    result = base.blend(src, dst, lambda s, d: s[:, :, :3])
    scale = max(np.max(src), np.max(dst), 1.0)
    expected = (
        np.concatenate([src, np.ones((*src.shape[:2], 1), dtype=src.dtype)], axis=2)
        / scale
    )
    assert np.allclose(result, expected)
    assert result.dtype == np.float16
    assert result.shape == (2, 2, 4)

    # Opacity < 1, blending applied
    base.opacity = 0.3
    result_opacity = base.blend(src, dst, lambda s, d: s[:, :, :3])
    expected_opacity = 0.3 * expected + 0.7 * (
        np.concatenate([dst, np.ones((*dst.shape[:2], 1), dtype=dst.dtype)], axis=2)
        / scale
    )
    assert np.allclose(result_opacity, expected_opacity)
    assert result_opacity.dtype == np.float16
    assert result_opacity.shape == (2, 2, 4)


def test_make_blend_function_default_path():
    def dummy_blend(s, d):
        return s

    func = bf.make_blend_function(dummy_blend)

    src = np.ones((2, 2, 3), dtype=np.float16)
    dst = np.zeros((2, 2, 3), dtype=np.float16)

    # Default blend with type checks disabled
    result = func(src, dst, disable_type_checks=True)
    scale = max(np.max(src), np.max(dst), 1.0)
    expected = (
        np.concatenate([src, np.ones((*src.shape[:2], 1), dtype=src.dtype)], axis=2)
        / scale
    )
    assert np.allclose(result, expected)
    assert result.dtype == np.float16
    assert result.shape == (2, 2, 4)

    # Blend with opacity < 1
    result_opacity = func(src, dst, opacity=0.5, disable_type_checks=True)
    expected_opacity = 0.5 * expected + 0.5 * (
        np.concatenate([dst, np.ones((*dst.shape[:2], 1), dtype=dst.dtype)], axis=2)
        / scale
    )
    assert np.allclose(result_opacity, expected_opacity)
    assert result_opacity.dtype == np.float16
    assert result_opacity.shape == (2, 2, 4)


def test_blend_dtype_respecting_input_and_output():
    src = np.ones((2, 2, 4), dtype=np.float32)
    dst = np.zeros((2, 2, 4), dtype=np.float32)
    dst[..., 3] = 1.0  # fully opaque

    func = bf.make_blend_function(lambda s, d: s)

    # input_dtype=float16, output_dtype=float32
    result = func(
        src,
        dst,
        input_dtype=np.float16,
        output_dtype=np.float32,
        disable_type_checks=True,
    )
    scale = max(np.max(src.astype(np.float16)), np.max(dst.astype(np.float16)), 1.0)
    expected = (src.astype(np.float16) / scale).astype(np.float32)

    # Fill alpha channel manually to match _compose_alpha behavior
    expected[..., 3] = 1.0

    assert np.allclose(result, expected)
    assert result.dtype == np.float32
    assert result.shape == (2, 2, 4)


@pytest.mark.parametrize("disable_type_checks", [True, False])
def test_prepare_type_checks_casting(disable_type_checks):
    blend = BlendBase()
    blend.disable_type_checks = disable_type_checks
    blend.fcn_name = "test_blend"
    blend.input_dtype = np.float16
    blend.opacity = 1.0

    src = np.ones((2, 2, 4), dtype=np.float64)
    dst = np.zeros((2, 2, 4), dtype=np.float64)

    src_out, dst_out, scale = blend._prepare(src, dst)

    assert src_out.dtype == np.float16
    assert dst_out.dtype == np.float16
    assert src_out.shape[0:2] == src.shape[0:2]
    assert dst_out.shape[0:2] == dst.shape[0:2]


def test_prepare_type_checks_enabled_no_cast():
    blend = BlendBase()
    blend.disable_type_checks = False
    blend.fcn_name = "test_blend"
    blend.input_dtype = np.float16
    blend.opacity = 1.0

    src = np.ones((2, 2, 4), dtype=np.float16)
    dst = np.zeros((2, 2, 4), dtype=np.float16)

    src_out, dst_out, scale = blend._prepare(src, dst)
    assert np.shares_memory(src, src_out)
    assert np.shares_memory(dst, dst_out)


def test_prepare_type_checks_enabled_invalid_shape_and_channels():
    blend = BlendBase()
    blend.disable_type_checks = False
    blend.fcn_name = "test_blend"
    blend.input_dtype = np.float16
    blend.opacity = 1.0

    # Invalid shape
    src2d = np.ones((2, 2), dtype=np.float16)
    dst2d = np.zeros((2, 2), dtype=np.float16)
    with pytest.raises(TypeError, match=r"Expected: 3D array"):
        blend._prepare(src2d, dst2d)

    # Invalid channels
    src3c = np.ones((2, 2, 3), dtype=np.float16)
    dst3c = np.zeros((2, 2, 3), dtype=np.float16)
    with pytest.raises(TypeError, match=r"Expected: 4 layers"):
        blend._prepare(src3c, dst3c)


@pytest.mark.parametrize("blend_name", blend_names)
def test_blend_functions_opacity_zero(src_image, dst_images, blend_name):
    if blend_name not in dst_images or blend_name not in blend_modes_with_opacity:
        pytest.skip()
    result = getattr(bf, blend_name)(
        src_image,
        dst_images[blend_name],
        opacity=0.0,
        disable_type_checks=True,
        dtype=np.float16,
    )
    np.testing.assert_allclose(
        result, dst_images[blend_name].astype(np.float16), rtol=1e-3
    )
    assert result.shape == src_image.shape
    assert result.dtype == np.float16


@pytest.mark.parametrize("blend_name", blend_names)
def test_blend_functions_opacity_one(src_image, dst_images, blend_name):
    if blend_name not in dst_images or blend_name not in blend_modes_with_opacity:
        pytest.skip()
    result = getattr(bf, blend_name)(
        src_image,
        dst_images[blend_name],
        opacity=1.0,
        disable_type_checks=True,
        dtype=np.float16,
    )
    assert result.shape == src_image.shape
    assert result.dtype == np.float16
    if blend_name not in blend_modes_allowing_equal:
        assert not np.allclose(result, dst_images[blend_name].astype(np.float16))


@pytest.mark.parametrize("blend_name", blend_names)
@pytest.mark.parametrize("opacity", [0.25, 0.5, 0.75])
def test_blend_functions_opacity_mid(src_image, dst_images, blend_name, opacity):
    if blend_name not in dst_images or blend_name not in blend_modes_with_opacity:
        pytest.skip()
    result = getattr(bf, blend_name)(
        src_image,
        dst_images[blend_name],
        opacity=opacity,
        disable_type_checks=True,
        dtype=np.float16,
    )
    assert result.shape == src_image.shape
    assert result.dtype == np.float16
    assert (result >= 0).all() and (result <= 1).all()


def test_burn_blend_cases():
    # basic case
    s = np.array([[0.5, 1.0], [0.2, 0.0]], dtype=np.float32)
    d = np.array([[0.2, 0.3], [0.9, 0.5]], dtype=np.float32)
    r = bf.burn_blend(s, d)
    assert r.shape == s.shape
    assert r.dtype == s.dtype
    assert (r >= 0).all() and (r <= 1).all()
    assert r[0, 0] == 0
    assert np.isclose(r[0, 1], 0.3)
    assert r[1, 1] == 0

    # all ones
    s1 = np.ones((3, 3), dtype=np.float32)
    d1 = np.ones((3, 3), dtype=np.float32)
    assert np.allclose(bf.burn_blend(s1, d1), 1)

    # all zeros
    s0 = np.zeros((2, 2), dtype=np.float32)
    d0 = np.zeros((2, 2), dtype=np.float32)
    assert np.all(bf.burn_blend(s0, d0) == 0)
