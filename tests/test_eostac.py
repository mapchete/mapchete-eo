import xarray as xr
from mapchete.formats import available_input_formats


def test_format_available():
    assert "EOSTAC" in available_input_formats()


def test_stac_read_xarray(stac_mapchete):
    with stac_mapchete.process_mp(tile=(13, 2385, 8833)).open("inp") as cube:
        assert isinstance(cube.read(assets=["B04", "B03", "B02"]), xr.Dataset)
