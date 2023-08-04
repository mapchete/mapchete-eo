from mapchete.formats import available_input_formats
import pytest
import xarray as xr

from mapchete_eo.platforms.sentinel2.config import DriverConfig


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
def test_s2_read_xarray(sentinel2_mapchete, test_tile):
    with sentinel2_mapchete.process_mp(tile=test_tile).open("inp") as cube:
        assert isinstance(cube.read(assets=["red"]), xr.Dataset)
