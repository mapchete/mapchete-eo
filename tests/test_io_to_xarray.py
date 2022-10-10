import pytest
from shapely.geometry import shape
import xarray as xr
from mapchete.tile import BufferedTilePyramid

from mapchete_eo.io import (
    asset_to_xarray,
    item_to_xarray,
    items_to_xarray,
    eo_bands_to_assets_indexes,
)


def test_s2_eo_bands_to_assets_indexes(s2_stac_item):
    eo_bands = ["B04", "B03", "B02"]
    assets_indexes = eo_bands_to_assets_indexes(s2_stac_item, eo_bands)
    assert len(eo_bands) == len(assets_indexes)
    for eo_band, (asset, index) in zip(eo_bands, assets_indexes):
        assert eo_band == asset
        assert index == 1


def test_s2_eo_bands_to_assets_indexes_invalid_band(s2_stac_item):
    eo_bands = ["foo"]
    with pytest.raises(KeyError):
        eo_bands_to_assets_indexes(s2_stac_item, eo_bands)


def test_s2_asset_to_xarray(s2_stac_item):
    tile = BufferedTilePyramid("geodetic").tile_from_xy(14.09662, 37.58410, zoom=13)
    asset = "B01"
    darr = asset_to_xarray(item=s2_stac_item, asset=asset, tile=tile, nodataval=0)
    assert isinstance(darr, xr.DataArray)
    assert darr.attrs.get("_FillValue") == 0
    assert darr.name == "B01"
    assert darr.any()


def test_s2_item_to_xarray(s2_stac_item):
    tile = BufferedTilePyramid("geodetic").tile_from_xy(14.09662, 37.58410, zoom=13)
    assets = ["B04", "B03", "B02"]
    ds = item_to_xarray(
        item=s2_stac_item, assets=assets, tile=tile, nodatavals=[0, 0, 0]
    )
    assert isinstance(ds, xr.Dataset)
    assert set(ds.data_vars) == set(assets)
    assert ds.any()


def test_s2_items_to_xarray(s2_stac_item):
    tile = BufferedTilePyramid("geodetic").tile_from_xy(14.09662, 37.58410, zoom=13)
    assets = ["B04", "B03", "B02"]
    ds = items_to_xarray(
        items=[s2_stac_item], assets=assets, tile=tile, nodatavals=[0, 0, 0]
    )
    assert isinstance(ds, xr.Dataset)
    assert set(ds.data_vars) == set([s2_stac_item.id])
    assert ds.any()


def test_s2_item_to_xarray_eo_bands(s2_stac_item):
    tile = BufferedTilePyramid("geodetic").tile_from_xy(14.09662, 37.58410, zoom=13)
    eo_bands = ["B04", "B03", "B02"]
    ds = item_to_xarray(
        item=s2_stac_item, eo_bands=eo_bands, tile=tile, nodatavals=[0, 0, 0]
    )
    assert isinstance(ds, xr.Dataset)
    assert set(ds.data_vars) == set(eo_bands)
    assert ds.any()


def test_s2_items_to_xarray_eo_bands(s2_stac_item):
    tile = BufferedTilePyramid("geodetic").tile_from_xy(14.09662, 37.58410, zoom=13)
    eo_bands = ["B04", "B03", "B02"]
    ds = items_to_xarray(
        items=[s2_stac_item], eo_bands=eo_bands, tile=tile, nodatavals=[0, 0, 0]
    )
    assert isinstance(ds, xr.Dataset)
    assert set(ds.data_vars) == set([s2_stac_item.id])
    assert ds.any()


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


def test_pf_item_to_xarray_eo_bands(pf_sr_stac_item):
    point = shape(pf_sr_stac_item.geometry).centroid
    tile = BufferedTilePyramid("geodetic").tile_from_xy(point.x, point.y, zoom=13)
    eo_bands = ["B4", "B3", "B2"]
    ds = item_to_xarray(
        item=pf_sr_stac_item, eo_bands=eo_bands, tile=tile, nodatavals=[0, 0, 0]
    )
    assert isinstance(ds, xr.Dataset)
    assert set(ds.data_vars) == set(eo_bands)
    assert ds.any()
