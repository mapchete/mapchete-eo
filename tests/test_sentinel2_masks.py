import pytest
import xarray as xr

from mapchete_eo.types import MergeMethod
from mapchete_eo.platforms.sentinel2.masks import (
    product_masks_to_slices,
    masks_to_xarray,
)
from mapchete_eo.platforms.sentinel2.product import S2Product


@pytest.mark.parametrize(
    "merge_method",
    [MergeMethod.first, MergeMethod.all],
)
def test_masks_to_xarray(s2_stac_item, test_tile, merge_method):
    ds = masks_to_xarray(
        products=[S2Product.from_stac_item(s2_stac_item)],
        grid=test_tile,
        merge_method=merge_method,
    )
    assert isinstance(ds, xr.Dataset)
    assert set(ds.data_vars) == set([s2_stac_item.id])
    assert ds.any()


def test_masks_to_slices(s2_stac_items):
    slices = product_masks_to_slices(
        [S2Product.from_stac_item(item) for item in s2_stac_items],
        group_by_property="day",
    )
    for slice_ in slices:
        assert len(slice_.products) > 1
        for product in slice_.products:
            assert slice_.name == product.item.datetime.day
