import numpy.ma as ma
import pytest
from mapchete.tile import BufferedTile

from mapchete_eo.image_operations import FillSelectionMethod
from mapchete_eo.processes import (
    dtype_scale,
    eoxcloudless_mosaic,
    eoxcloudless_mosaic_merge,
    eoxcloudless_rgb_map,
    eoxcloudless_sentinel2_color_correction,
)


def test_eoxcloudless_8bit_dtype_scale_mapchete(eoxcloudless_8bit_dtype_scale_mapchete):
    process_mp = eoxcloudless_8bit_dtype_scale_mapchete.process_mp()
    output = dtype_scale.execute(process_mp)
    assert isinstance(output, ma.MaskedArray)
    assert not output.mask.any()
    assert ma.mean(output) < 100


@pytest.mark.parametrize("fillnodata", [True, False])
@pytest.mark.parametrize("fillnodata_method", [FillSelectionMethod.all, "all"])
@pytest.mark.parametrize("desert_color_correction_flag", [True, False])
def test_eoxcloudless_sentinel2_color_correction(
    eoxcloudless_sentinel2_color_correction_mapchete,
    fillnodata,
    fillnodata_method,
    desert_color_correction_flag,
):
    process_mp = eoxcloudless_sentinel2_color_correction_mapchete.process_mp()
    output = eoxcloudless_sentinel2_color_correction.execute(
        process_mp,
        fillnodata=fillnodata,
        fillnodata_method=fillnodata_method,
        desert_color_correction_flag=desert_color_correction_flag,
    )
    assert isinstance(output, ma.MaskedArray)
    assert not output.mask.any()
    assert ma.mean(output) < 200


def test_eoxcloudless_rgb_map(eoxcloudless_rgb_map_mapchete):
    process_mp = eoxcloudless_rgb_map_mapchete.process_mp()
    output = eoxcloudless_rgb_map.execute(
        process_mp,
    )
    assert isinstance(output, ma.MaskedArray)
    assert not output.mask.any()
    assert ma.mean(output) < 200


def test_eoxcloudless_rgb_map_mosaic_mask(eoxcloudless_rgb_map_mapchete):
    process_mp = eoxcloudless_rgb_map_mapchete.process_mp(tile=(6, 56, 103))
    output = eoxcloudless_rgb_map.execute(
        process_mp,
    )
    assert isinstance(output, ma.MaskedArray)
    assert not output.mask.any()
    assert ma.min(output) == 255
    assert ma.mean(output) == 255
    assert ma.max(output) == 255


@pytest.mark.remote
def test_eoxcloudless_mosaic(eoxcloudless_mosaic_mapchete):
    process_mp = eoxcloudless_mosaic_mapchete.process_mp()
    # calling the execute() function directly from the process module means
    # we have to provide all kwargs usually found in the process_parameters
    output = eoxcloudless_mosaic.execute(
        process_mp,
        assets=["red", "green", "blue", "nir"],
        mask_config=dict(scl_classes=["vegetation"]),
    )
    assert isinstance(output, ma.MaskedArray)
    assert output.mask.any()
    assert ma.mean(output) > 200


def test_eoxcloudless_mosaic_regions_merge(eoxcloudless_mosaic_regions_merge_mapchete):
    process_mp = eoxcloudless_mosaic_regions_merge_mapchete.process_mp()
    # calling the execute() function directly from the process module means
    # we have to provide all kwargs usually found in the process_parameters
    output = eoxcloudless_mosaic_merge.execute(
        process_mp,
        assets=["red", "green", "blue"],
    )
    assert isinstance(output, ma.MaskedArray)
    assert not output.mask.all()
    assert ma.mean(output) > 200
