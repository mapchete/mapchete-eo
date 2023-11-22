import numpy.ma as ma

from mapchete_eo.platforms.sentinel2.config import parse_mask_config
from mapchete_eo.platforms.sentinel2.masks import read_masks
from mapchete_eo.platforms.sentinel2.product import S2Product


def test_read_single_product_mask(s2_stac_item, test_tile):
    product = S2Product(s2_stac_item)
    product_read_kwargs = dict(
        mask_config=parse_mask_config(
            dict(
                footprint=True,
                l1c_cloud_type="all",
                cloud_probability_threshold=15,
                cloud_probability_resolution=60,
            )
        )
    )
    arr = product.read_np_array(
        grid=test_tile,
        nodatavals=[0, 0, 0],
        mask_config=product_read_kwargs["mask_config"],
        only_mask=True,
    )
    assert isinstance(arr, ma.MaskedArray)
    assert arr.any()
    assert not arr.mask.all()


def test_read_masks(s2_stac_item, test_tile):
    product = S2Product(s2_stac_item)
    product_read_kwargs = dict(
        mask_config=parse_mask_config(
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
