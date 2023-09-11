import pytest
import xarray as xr
from mapchete.tile import BufferedTilePyramid
from shapely.geometry import shape

from mapchete_eo.io import (
    asset_to_xarray,
    get_item_property,
    group_products_per_property,
    item_to_xarray,
    products_to_xarray,
)
from mapchete_eo.product import EOProduct


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
    ds = products_to_xarray(
        products=[EOProduct.from_stac_item(s2_stac_item)],
        assets=assets,
        tile=test_tile,
        nodatavals=[0, 0, 0],
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


def test_s2_products_to_xarray_eo_bands(s2_stac_item, test_tile):
    eo_bands = ["red", "green", "blue"]
    ds = products_to_xarray(
        products=[EOProduct(s2_stac_item)],
        eo_bands=eo_bands,
        tile=test_tile,
        nodatavals=[0, 0, 0],
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


def test_group_products_per_property_day(s2_stac_items):
    grouped = group_products_per_property(
        [EOProduct.from_stac_item(item) for item in s2_stac_items], "day"
    )
    for property, products in grouped.items():
        assert len(products) > 1
        for product in products:
            assert property == product.item.datetime.day


def test_s2_products_to_xarray_merge_date(s2_stac_items, test_tile):
    eo_bands = ["red", "green", "blue"]
    ds = products_to_xarray(
        products=[EOProduct.from_stac_item(item) for item in s2_stac_items],
        eo_bands=eo_bands,
        tile=test_tile,
        merge_products_by="date",
    )
    assert len(ds.data_vars) == 2
    assert isinstance(ds, xr.Dataset)


@pytest.mark.parametrize(
    "merge_method",
    ["first", "average"],
)
def test_s2_products_to_xarray_merge_datastrip_id(
    s2_stac_items, test_tile, merge_method
):
    eo_bands = ["red", "green", "blue"]
    ds = products_to_xarray(
        products=[EOProduct.from_stac_item(item) for item in s2_stac_items],
        eo_bands=eo_bands,
        tile=test_tile,
        merge_products_by="s2:datastrip_id",
        merge_method=merge_method,
    )
    assert len(ds) == 2
    assert isinstance(ds, xr.Dataset)
    assert "s2:datastrip_id" in ds.coords


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
