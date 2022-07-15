import xarray as xr
from mapchete.tile import BufferedTilePyramid

from mapchete_eo.io import asset_to_xarray, item_to_xarray, items_to_xarray


def test_asset_to_xarray(s2_stac_item):
    tile = BufferedTilePyramid("geodetic").tile_from_xy(14.09662, 37.58410, zoom=13)
    darr = asset_to_xarray(item=s2_stac_item, asset="B01", tile=tile, nodataval=0)
    assert isinstance(darr, xr.DataArray)
    assert darr.attrs.get("_FillValue") == 0
    assert darr.name == "B01"
    assert darr.any()


def test_item_to_xarray(s2_stac_item):
    tile = BufferedTilePyramid("geodetic").tile_from_xy(14.09662, 37.58410, zoom=13)
    assets = ["B04", "B03", "B02"]
    ds = item_to_xarray(
        item=s2_stac_item, assets=assets, tile=tile, nodatavals=[0, 0, 0]
    )
    assert isinstance(ds, xr.Dataset)
    assert set(ds.data_vars) == set(assets)
    assert ds.any()


def test_items_to_xarray(s2_stac_item):
    tile = BufferedTilePyramid("geodetic").tile_from_xy(14.09662, 37.58410, zoom=13)
    assets = ["B04", "B03", "B02"]
    ds = items_to_xarray(
        items=[s2_stac_item], assets=assets, tile=tile, nodatavals=[0, 0, 0]
    )
    assert isinstance(ds, xr.Dataset)
    assert set(ds.data_vars) == set([s2_stac_item.id])
    assert ds.any()
