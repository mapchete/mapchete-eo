import numpy.ma as ma
import pytest


def test_eoxcloudless_8bit_dtype_scale_mapchete(eoxcloudless_8bit_dtype_scale_mapchete):
    mp = eoxcloudless_8bit_dtype_scale_mapchete.mp()
    zoom = max(mp.config.zoom_levels)
    # # tile containing data
    tile = next(mp.get_process_tiles(zoom))
    output = mp.execute(tile)
    assert isinstance(output, ma.MaskedArray)
    assert not output.mask.any()
    assert ma.mean(output) < 100


@pytest.mark.parametrize(
    "method", ["brightness", "max_ndvi", "weighted_avg", "ndvi_linreg"]
)
def test_eoxcloudless_mosaic_mapchete(eoxcloudless_mosaic_mapchete, method):
    eoxcloudless_mosaic_mapchete.dict["process_parameters"]["method"] = method
    mp = eoxcloudless_mosaic_mapchete.mp()
    zoom = max(mp.config.zoom_levels)
    # tile containing data
    tile = next(mp.get_process_tiles(zoom))
    output = mp.execute(tile)
    assert isinstance(output, ma.MaskedArray)
    assert not output.mask.any()
    assert ma.mean(output) > 200
