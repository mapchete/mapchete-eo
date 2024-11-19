from datetime import datetime

import pytest
from mapchete.path import MPath
from mapchete.types import Bounds
from pytest_lazyfixture import lazy_fixture
from shapely.geometry import shape

from mapchete_eo.io import get_item_property, item_fix_footprint, products_to_slices
from mapchete_eo.io.path import (
    ProductPathGenerationMethod,
    asset_mpath,
    get_product_cache_path,
)
from mapchete_eo.io.products import Slice
from mapchete_eo.product import EOProduct
from mapchete_eo.sort import TargetDateSort


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


@pytest.mark.parametrize("path_generation_method", ProductPathGenerationMethod)
def test_get_product_cache_path(s2_stac_item, tmp_mpath, path_generation_method):
    path = get_product_cache_path(
        s2_stac_item, tmp_mpath, path_generation_method=path_generation_method
    )
    assert isinstance(path, MPath)


@pytest.mark.parametrize(
    "item", [lazy_fixture("s2_stac_item"), lazy_fixture("s2_remote_stac_item")]
)
@pytest.mark.parametrize("absolute_out_path", [True, False])
@pytest.mark.parametrize("relative_asset_path", [True, False])
def test_asset_mpath(item, absolute_out_path, relative_asset_path):
    asset = "red"
    if relative_asset_path:
        item.assets[asset].href = MPath(item.assets[asset].href).name
    path = asset_mpath(item, asset, absolute_path=absolute_out_path)
    assert isinstance(path, MPath)
    if absolute_out_path:
        assert path.is_absolute()

    # don't test file existance on this because per definition, file cannot be found here:
    if relative_asset_path and not absolute_out_path:
        return

    assert path.exists()


def test_slice(s2_stac_items):
    name = "foo"
    slice_ = Slice(
        name=name, products=[EOProduct.from_stac_item(item) for item in s2_stac_items]
    )
    assert slice_.name == name
    assert slice_.products
    assert isinstance(slice_.datetime, datetime)
    assert isinstance(slice_.properties, dict)


def test_products_to_slices(s2_stac_items):
    slices = products_to_slices(
        [EOProduct.from_stac_item(item) for item in s2_stac_items],
        group_by_property="day",
    )
    for slice_ in slices:
        assert len(slice_.products) > 1
        for product in slice_.products:
            assert slice_.name == product.item.datetime.day


def test_products_to_slices_empty():
    slices = products_to_slices([], group_by_property="day", sort=TargetDateSort())
    for slice_ in slices:
        assert len(slice_.products) > 1
        for product in slice_.products:
            assert slice_.name == product.item.datetime.day


@pytest.mark.parametrize(
    "item",
    [
        lazy_fixture("antimeridian_item1"),
        lazy_fixture("antimeridian_item2"),
        lazy_fixture("antimeridian_item4"),
    ],
)
def test_item_fix_antimeridian_footprint(item):
    fixed_geom = shape(item_fix_footprint(item).geometry)
    assert fixed_geom.geom_type == "MultiPolygon"
    # make sure it touches the Antimeridian
    bounds = Bounds.from_inp(fixed_geom)
    assert bounds.left == -180
    assert bounds.right == 180
