import pytest
from shapely.geometry import shape
import xarray as xr
from mapchete.tile import BufferedTilePyramid

from mapchete_eo.io import (
    asset_to_xarray,
    item_to_xarray,
    items_to_xarray,
    eo_bands_to_assets_indexes,
    group_items_per_property,
    get_item_property,
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


def test_s2_asset_to_xarray(s2_stac_item, test_tile):
    asset = "B01"
    darr = asset_to_xarray(item=s2_stac_item, asset=asset, tile=test_tile, nodataval=0)
    assert isinstance(darr, xr.DataArray)
    assert darr.attrs.get("_FillValue") == 0
    assert darr.name == "B01"
    assert darr.any()


def test_s2_item_to_xarray(s2_stac_item, test_tile):
    assets = ["B04", "B03", "B02"]
    ds = item_to_xarray(
        item=s2_stac_item, assets=assets, tile=test_tile, nodatavals=[0, 0, 0]
    )
    assert isinstance(ds, xr.Dataset)
    assert set(ds.data_vars) == set(assets)
    assert ds.any()


def test_s2_items_to_xarray(s2_stac_item, test_tile):
    assets = ["B04", "B03", "B02"]
    ds = items_to_xarray(
        items=[s2_stac_item], assets=assets, tile=test_tile, nodatavals=[0, 0, 0]
    )
    assert isinstance(ds, xr.Dataset)
    assert set(ds.data_vars) == set([s2_stac_item.id])
    assert ds.any()


def test_s2_item_to_xarray_eo_bands(s2_stac_item, test_tile):
    eo_bands = ["B04", "B03", "B02"]
    ds = item_to_xarray(
        item=s2_stac_item, eo_bands=eo_bands, tile=test_tile, nodatavals=[0, 0, 0]
    )
    assert isinstance(ds, xr.Dataset)
    assert set(ds.data_vars) == set(eo_bands)
    assert ds.any()


def test_s2_items_to_xarray_eo_bands(s2_stac_item, test_tile):
    eo_bands = ["B04", "B03", "B02"]
    ds = items_to_xarray(
        items=[s2_stac_item], eo_bands=eo_bands, tile=test_tile, nodatavals=[0, 0, 0]
    )
    assert isinstance(ds, xr.Dataset)
    assert set(ds.data_vars) == set([s2_stac_item.id])
    assert ds.any()


def test_get_item_property_date(s2_stac_item):
    assert get_item_property(s2_stac_item, "day") == s2_stac_item.datetime.day
    assert get_item_property(s2_stac_item, "month") == s2_stac_item.datetime.month
    assert get_item_property(s2_stac_item, "year") == s2_stac_item.datetime.year
    assert get_item_property(s2_stac_item, "datetime") == s2_stac_item.datetime
    assert (
        get_item_property(s2_stac_item, "date")
        == s2_stac_item.datetime.date().isoformat()
    )


def test_get_item_property_properties(s2_stac_item):
    for property, value in {
        "platform": "sentinel-2a",
        "constellation": "sentinel-2",
        "instruments": ["msi"],
        "gsd": 10,
        "view:off_nadir": 0,
        "proj:epsg": 32633,
        "sentinel:utm_zone": 33,
        "sentinel:latitude_band": "U",
        "sentinel:grid_square": "WP",
        "sentinel:sequence": "0",
        "sentinel:product_id": "S2A_MSIL2A_20220405T100031_N0400_R122_T33UWP_20220405T120515",
        "sentinel:data_coverage": 100,
        "eo:cloud_cover": 89.48,
        "sentinel:valid_cloud_cover": True,
        "sentinel:processing_baseline": "04.00",
        "sentinel:boa_offset_applied": True,
        "created": "2022-04-05T17:55:51.345Z",
        "updated": "2022-04-05T17:55:51.345Z",
    }.items():
        assert get_item_property(s2_stac_item, property) == value


def test_get_item_property_extra_fields(s2_stac_item):
    for property, value in {"stac_extensions": ["eo", "view", "proj"]}.items():
        assert get_item_property(s2_stac_item, property) == value


def test_group_items_per_property_day(s2_stac_items):
    grouped = group_items_per_property(s2_stac_items, "day")
    for property, items in grouped.items():
        assert len(items) > 1
        for item in items:
            assert property == item.datetime.day


def test_s2_items_to_xarray_merge(s2_stac_items, test_tile):
    eo_bands = ["B04"]
    ds = items_to_xarray(
        items=s2_stac_items,
        eo_bands=eo_bands,
        tile=test_tile,
        nodatavals=[0, 0, 0],
        merge_items_by="date",
    )
    assert isinstance(ds, xr.Dataset)


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
