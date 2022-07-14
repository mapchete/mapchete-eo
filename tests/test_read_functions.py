import xarray as xr
from mapchete.tile import BufferedTilePyramid

from mapchete_eo.read import read_asset, read_item, read_items


def test_read_asset(s2_stac_item):
    tile = BufferedTilePyramid("geodetic").tile_from_xy(14.09662, 37.58410, zoom=13)
    darr = read_asset(item=s2_stac_item, asset="B01", tile=tile, nodataval=0)
    assert isinstance(darr, xr.DataArray)
    assert darr.attrs.get("_FillValue") == 0
    assert darr.name == "B01"
    assert darr.any()


def test_read_item(s2_stac_item):
    tile = BufferedTilePyramid("geodetic").tile_from_xy(14.09662, 37.58410, zoom=13)
    assets = ["B04", "B03", "B02"]
    ds = read_item(item=s2_stac_item, assets=assets, tile=tile, nodatavals=[0, 0, 0])
    assert isinstance(ds, xr.Dataset)
    assert set(ds.data_vars) == set(assets)
    assert ds.any()


def test_read_items(s2_stac_item):
    tile = BufferedTilePyramid("geodetic").tile_from_xy(14.09662, 37.58410, zoom=13)
    assets = ["B04", "B03", "B02"]
    ds = read_items(
        items=[s2_stac_item], assets=assets, tile=tile, nodatavals=[0, 0, 0]
    )
    assert isinstance(ds, xr.Dataset)
    assert set(ds.data_vars) == set([s2_stac_item.id])
    assert ds.any()
