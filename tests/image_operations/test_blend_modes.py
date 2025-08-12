import pytest
import numpy as np
import mapchete_eo.image_operations.blend_modes.blending_functions as bf  # Replace with your actual blend functions module

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
