from mapchete.io.raster import ReferencedRaster
import numpy.ma as ma
import pytest
import xarray as xr


from mapchete_eo.platforms.sentinel2.config import MaskConfig
from mapchete_eo.platforms.sentinel2.masks import (
    masks_to_xarray,
    product_masks_to_slices,
    read_masks,
)
from mapchete_eo.platforms.sentinel2.product import S2Product
from mapchete_eo.types import MergeMethod


def test_read_single_product_mask(s2_stac_item, test_tile):
    product = S2Product(s2_stac_item)
    product_read_kwargs = dict(
        mask_config=MaskConfig.parse(
            dict(
                footprint=True,
                l1c_cloud_type="all",
                cloud_probability_threshold=15,
                cloud_probability_resolution=60,
            )
        )
    )
    raster = product.get_mask(
        grid=test_tile,
        mask_config=product_read_kwargs["mask_config"],
    )
    assert isinstance(raster, ReferencedRaster)
    assert raster.array.any()
    assert not raster.array.all()


def test_read_masks(s2_stac_item, test_tile):
    product = S2Product(s2_stac_item)
    product_read_kwargs = dict(
        mask_config=MaskConfig.parse(
            dict(
                footprint=True,
                l1c_cloud_type="all",
                cloud_probability_threshold=15,
                cloud_probability_resolution=60,
            )
        )
    )
    arr = read_masks(
        products=[product],
        grid=test_tile,
        nodatavals=[0, 0, 0],
        product_read_kwargs=product_read_kwargs,
    )
    assert isinstance(arr, ma.MaskedArray)
    assert arr.any()
    assert not arr.mask.all()


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
