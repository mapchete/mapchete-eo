from mapchete_eo.platforms.sentinel2.masks import product_masks_to_slices
from mapchete_eo.platforms.sentinel2.product import S2Product


def test_masks_to_slices(s2_stac_items):
    slices = product_masks_to_slices(
        [S2Product.from_stac_item(item) for item in s2_stac_items],
        group_by_property="day",
    )
    for slice_ in slices:
        assert len(slice_.products) > 1
        for product in slice_.products:
            assert slice_.name == product.item.datetime.day
