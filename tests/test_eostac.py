import xarray as xr
from mapchete.formats import available_input_formats


def test_format_available():
    assert "EOSTAC_DEV" in available_input_formats()


def test_stac_read_xarray(stac_mapchete, test_tile):
    with stac_mapchete.process_mp(tile=test_tile).open("inp") as src:
        cube = src.read(assets=["red", "green", "blue"])
        assert isinstance(cube, xr.Dataset)
        assert cube.to_array().any()
