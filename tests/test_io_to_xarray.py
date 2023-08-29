import pytest
import xarray as xr
from mapchete.tile import BufferedTilePyramid
from shapely.geometry import shape

from mapchete_eo.io import (
    asset_to_xarray,
    eo_bands_to_assets_indexes,
    get_item_property,
    group_items_per_property,
    item_to_xarray,
    items_to_xarray,
)


def test_s2_eo_bands_to_assets_indexes(s2_stac_item):
    eo_bands = ["red", "green", "blue"]
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
    asset = "blue"
    darr = asset_to_xarray(item=s2_stac_item, asset=asset, tile=test_tile, nodataval=0)
    assert isinstance(darr, xr.DataArray)
    assert darr.attrs.get("_FillValue") == 0
    assert darr.name == "blue"
    assert darr.any()


def test_s2_item_to_xarray(s2_stac_item, test_tile):
    assets = ["red", "green", "blue"]
    ds = item_to_xarray(
        item=s2_stac_item, assets=assets, tile=test_tile, nodatavals=[0, 0, 0]
    )
    assert isinstance(ds, xr.Dataset)
    assert set(ds.data_vars) == set(assets)
    assert ds.any()


def test_s2_items_to_xarray(s2_stac_item, test_tile):
    assets = ["red", "green", "blue"]
    ds = items_to_xarray(
        items=[s2_stac_item], assets=assets, tile=test_tile, nodatavals=[0, 0, 0]
    )
    assert isinstance(ds, xr.Dataset)
    assert set(ds.data_vars) == set([s2_stac_item.id])
    assert ds.any()


def test_s2_item_to_xarray_eo_bands(s2_stac_item, test_tile):
    eo_bands = ["red", "green", "blue"]
    ds = item_to_xarray(
        item=s2_stac_item, eo_bands=eo_bands, tile=test_tile, nodatavals=[0, 0, 0]
    )
    assert isinstance(ds, xr.Dataset)
    assert set(ds.data_vars) == set(eo_bands)
    assert ds.any()


def test_s2_items_to_xarray_eo_bands(s2_stac_item, test_tile):
    eo_bands = ["red", "green", "blue"]
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


@pytest.mark.parametrize(
    "key",
    [
        "platform",
        "constellation",
        "instruments",
        "proj:epsg",
        "eo:cloud_cover",
        "mgrs:utm_zone",
        "mgrs:latitude_band",
        "mgrs:grid_square",
        "s2:sequence",
        "s2:granule_id",
        "s2:processing_baseline",
        "s2:datastrip_id",
        "earthsearch:boa_offset_applied",
        "created",
        "updated",
    ],
)
def test_get_item_property_properties(s2_stac_item, key):
    assert get_item_property(s2_stac_item, key) is not None


def test_get_item_property_extra_fields(s2_stac_item):
    assert isinstance(get_item_property(s2_stac_item, "stac_extensions"), list)


def test_group_items_per_property_day(s2_stac_items):
    grouped = group_items_per_property(s2_stac_items, "day")
    for property, items in grouped.items():
        assert len(items) > 1
        for item in items:
            assert property == item.datetime.day


def test_s2_items_to_xarray_merge_date(s2_stac_items, test_tile):
    eo_bands = ["red", "green", "blue"]
    ds = items_to_xarray(
        items=s2_stac_items,
        eo_bands=eo_bands,
        tile=test_tile,
        merge_items_by="date",
    )
    assert len(ds.data_vars) == 2
    assert isinstance(ds, xr.Dataset)


@pytest.mark.parametrize(
    "merge_method",
    ["first", "average"],
)
def test_s2_items_to_xarray_merge_datastrip_id(s2_stac_items, test_tile, merge_method):
    eo_bands = ["red", "green", "blue"]
    ds = items_to_xarray(
        items=s2_stac_items,
        eo_bands=eo_bands,
        tile=test_tile,
        merge_items_by="s2:datastrip_id",
        merge_method=merge_method,
    )
    assert len(ds) == 2
    assert isinstance(ds, xr.Dataset)
    assert "s2:datastrip_id" in ds.coords


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
