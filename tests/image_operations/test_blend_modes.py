import pytest
from mapchete_eo.image_operations.blend_modes import blending_functions as bf

blend_names = [
    "normal",
    "multiply",
    "screen",
    "darken_only",
    "lighten_only",
    "difference",
    "subtract",
    "divide",
    "grain_extract",
    "grain_merge",
    "overlay",
    "hard_light",
    "soft_light",
    "dodge",
    "burn",
    "addition",
]


@pytest.mark.parametrize("blend_name", blend_names)
def test_blend_functions_with_images(src_image, dst_images, blend_name):
    if blend_name not in dst_images:
        pytest.skip(f"No destination image for {blend_name}")

    dst_image = dst_images[blend_name]

    blend_func = getattr(bf, blend_name)
    result = blend_func(
        src_image,
        dst_image,
        opacity=1.0,
        disable_type_checks=True,
        dtype=src_image.dtype,
    )

    # Basic sanity checks
    assert result.shape == src_image.shape
    assert result.dtype == src_image.dtype
    assert (result >= 0).all() and (result <= 1).all()


@pytest.mark.parametrize("blend_name", blend_names)
def test_blend_functions_run_without_dst(src_image, dst_images, blend_name):
    # Run blend even if dst image missing, just check no error
    if blend_name in dst_images:
        pytest.skip(
            f"Destination image exists for {blend_name}, skipping run without dst test"
        )

    blend_func = getattr(bf, blend_name)
    # Use src_image as dst as fallback (to ensure it runs)
    result = blend_func(
        src_image,
        src_image,
        opacity=1.0,
        disable_type_checks=True,
        dtype=src_image.dtype,
    )

    assert result.shape == src_image.shape
    assert result.dtype == src_image.dtype
    assert (result >= 0).all() and (result <= 1).all()
