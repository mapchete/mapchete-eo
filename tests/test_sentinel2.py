from mapchete.formats import available_input_formats
import pytest
import xarray as xr


def test_format_available():
    assert "Sentinel-2" in available_input_formats()


@pytest.mark.webtest
def test_s2_read_xarray(sentinel2_mapchete, test_tile):
    with sentinel2_mapchete.process_mp(tile=test_tile).open("inp") as cube:
        assert isinstance(cube.read(assets=["red"]), xr.Dataset)
