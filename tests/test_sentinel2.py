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
def test_s2_read_xarray(sentinel2_mapchete):
    with sentinel2_mapchete.process_mp().open("inp") as cube:
        assert isinstance(cube.read(assets=["red"]), xr.Dataset)


def test_preprocessing(sentinel2_mapchete):
    mp = sentinel2_mapchete.mp()
    input_data = list(mp.config.inputs.values())[0]
    assert input_data.products

    tile_mp = sentinel2_mapchete.process_mp()
    assert tile_mp.open("inp").products
