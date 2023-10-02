import pytest

from mapchete_eo.io import get_item_property, group_products_per_property
from mapchete_eo.product import EOProduct


def test_group_products_per_property_day(s2_stac_items):
    grouped = group_products_per_property(
        [EOProduct.from_stac_item(item) for item in s2_stac_items], "day"
    )
    for property, products in grouped.items():
        assert len(products) > 1
        for product in products:
            assert property == product.item.datetime.day


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
