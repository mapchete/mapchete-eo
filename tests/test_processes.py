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


def test_eoxcloudless_mosaic_mapchete(eoxcloudless_mosaic_mapchete):
    mp = eoxcloudless_mosaic_mapchete.mp()
    zoom = max(mp.config.zoom_levels)
    # # tile containing data
    tile = next(mp.get_process_tiles(zoom))
    output = mp.execute(tile)
    assert isinstance(output, ma.MaskedArray)
    assert not output.mask.any()
    assert ma.mean(output) > 700
