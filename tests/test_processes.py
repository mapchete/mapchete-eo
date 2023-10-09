import numpy.ma as ma
import pytest

from mapchete_eo.processes import eoxcloudless_mosaic


def test_eoxcloudless_8bit_dtype_scale_mapchete(eoxcloudless_8bit_dtype_scale_mapchete):
    mp = eoxcloudless_8bit_dtype_scale_mapchete.mp()
    zoom = max(mp.config.zoom_levels)
    # # tile containing data
    tile = next(mp.get_process_tiles(zoom))
    output = mp.execute(tile)
    assert isinstance(output, ma.MaskedArray)
    assert not output.mask.any()
    assert ma.mean(output) < 100


def test_eoxcloudless_sentinel2_color_correction(
    eoxcloudless_sentinel2_color_correction_mapchete,
):
    mp = eoxcloudless_sentinel2_color_correction_mapchete.mp()
    zoom = max(mp.config.zoom_levels)
    # # tile containing data
    tile = next(mp.get_process_tiles(zoom))
    output = mp.execute(tile)
    assert isinstance(output, ma.MaskedArray)
    assert not output.mask.any()
    assert ma.mean(output) < 200


@pytest.mark.remote
def test_eoxcloudless_mosaic_mapchete(eoxcloudless_mosaic_mapchete):
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
