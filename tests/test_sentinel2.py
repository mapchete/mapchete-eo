from mapchete.formats import available_input_formats
import pytest
import xarray as xr


def test_format_available():
    assert "Sentinel-2" in available_input_formats()


@pytest.mark.webtest
def test_s2_read_xarray(sentinel2_mapchete):
    with sentinel2_mapchete.process_mp(tile=(13, 2385, 8833)).open("inp") as cube:
        assert isinstance(cube.read(assets=["B01"]), xr.Dataset)
