import numpy.ma as ma
import pytest
import xarray as xr
from mapchete.formats import available_input_formats

from mapchete_eo.platforms.sentinel2.config import DriverConfig
from mapchete_eo.platforms.sentinel2.types import L2ABand


def test_format_available():
    assert "Sentinel-2" in available_input_formats()


def test_config():
    conf = DriverConfig(
        format="Sentinel-2",
        start_time="2022-04-01",
        end_time="2022-04-10",
    )
    assert conf.dict()


@pytest.mark.remote
def test_remote_s2_read_xarray(sentinel2_mapchete):
    with sentinel2_mapchete.process_mp().open("inp") as cube:
        assert isinstance(cube.read(assets=["red"]), xr.Dataset)


def test_preprocessing(sentinel2_mapchete):
    mp = sentinel2_mapchete.mp()
    input_data = list(mp.config.inputs.values())[0]
    assert input_data.products

    tile_mp = sentinel2_mapchete.process_mp()
    assert tile_mp.open("inp").products


def test_read(sentinel2_stac_mapchete):
    s2_src = sentinel2_stac_mapchete.process_mp().open("inp")
    cube = s2_src.read(assets=["red", "green", "blue", "nir"])
    assert isinstance(cube, xr.Dataset)
    assert cube.to_array().any()


# def test_read_levelled(sentinel2_stac_mapchete):
#     s2_src = sentinel2_stac_mapchete.process_mp().open("inp")
#     cube = s2_src.read_levelled(["red", "green", "blue", "nir"], 2)
#     assert isinstance(cube, xr.Dataset)


# def test_read_ma(sentinel2_stac_mapchete):
#     s2_src = sentinel2_stac_mapchete.process_mp().open("inp")
#     cube = s2_src.read_ma(assets=["red", "green", "blue", "nir"])
#     assert isinstance(cube, ma.MaskedArray)


# def test_read_levelled_ma(sentinel2_stac_mapchete):
#     s2_src = sentinel2_stac_mapchete.process_mp().open("inp")
#     cube = s2_src.read_levelled_ma(["red", "green", "blue", "nir"])
#     assert cube.ndims == 4
#     assert isinstance(cube, ma.MaskedArray)
