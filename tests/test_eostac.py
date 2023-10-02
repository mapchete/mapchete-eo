import xarray as xr
from mapchete.formats import available_input_formats

from mapchete_eo.product import eo_bands_to_assets_indexes


# TODO:
# --> PF Elias:
# DataSet
# per band 1 DataArray
# each DataArray has 3 dimensions: time, x, y
def test_pf_eo_bands_to_assets_indexes(pf_sr_stac_item):
    eo_bands = ["B3", "B2", "B4"]
    assets_indexes = eo_bands_to_assets_indexes(pf_sr_stac_item, eo_bands)
    assert len(eo_bands) == len(assets_indexes)
    for band_index, (asset, index) in zip([1, 2, 4], assets_indexes):
        assert asset == "bands"
        assert band_index == index


def test_format_available():
    assert "EOSTAC_DEV" in available_input_formats()


def test_stac_read_xarray(stac_mapchete, test_tile):
    with stac_mapchete.process_mp(tile=test_tile).open("inp") as src:
        cube = src.read(assets=["red", "green", "blue"])
        assert isinstance(cube, xr.Dataset)
        assert cube.to_array().any()


def test_preprocessing(stac_mapchete):
    mp = stac_mapchete.mp()
    input_data = list(mp.config.inputs.values())[0]
    assert input_data.products

    tile_mp = stac_mapchete.process_mp()
    assert tile_mp.open("inp").products
