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
    asset = "coastal"
    darr = asset_to_xarray(item=s2_stac_item, asset=asset, tile=test_tile, nodataval=0)
    assert isinstance(darr, xr.DataArray)
    assert darr.attrs.get("_FillValue") == 0
    assert darr.name == "coastal"
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
    "key, expected_value",
    [
        ("platform", "sentinel-2a"),
        ("constellation", "sentinel-2"),
        ("instruments", ["msi"]),
        ("proj:epsg", 32633),
        ("eo:cloud_cover", 94.103563),
        ("mgrs:utm_zone", 33),
        ("mgrs:latitude_band", "U"),
        ("mgrs:grid_square", "WP"),
        ("s2:sequence", "0"),
        (
            "s2:granule_id",
            "S2A_OPER_MSI_L2A_TL_VGS4_20220405T120515_A035440_T33UWP_N04.00",
        ),
        ("s2:processing_baseline", "04.00"),
        (
            "s2:datastrip_id",
            "S2A_OPER_MSI_L2A_DS_VGS4_20220405T120515_S20220405T100408_N04.00",
        ),
        ("earthsearch:boa_offset_applied", True),
        ("created", "2022-11-06T12:37:04.689Z"),
        ("updated", "2022-11-06T12:37:04.689Z"),
    ],
)
def test_get_item_property_properties(s2_stac_item, key, expected_value):
    assert get_item_property(s2_stac_item, key) == expected_value


def test_get_item_property_extra_fields(s2_stac_item):
    for property, value in {
        "stac_extensions": [
            "https://stac-extensions.github.io/eo/v1.1.0/schema.json",
            "https://stac-extensions.github.io/raster/v1.1.0/schema.json",
            "https://stac-extensions.github.io/mgrs/v1.0.0/schema.json",
            "https://stac-extensions.github.io/processing/v1.1.0/schema.json",
            "https://stac-extensions.github.io/view/v1.0.0/schema.json",
            "https://stac-extensions.github.io/grid/v1.1.0/schema.json",
            "https://stac-extensions.github.io/projection/v1.1.0/schema.json",
        ]
    }.items():
        assert get_item_property(s2_stac_item, property) == value


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
