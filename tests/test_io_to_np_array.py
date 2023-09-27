import numpy.ma as ma
import pytest

from mapchete_eo.io import products_to_np_array
from mapchete_eo.product import EOProduct
from mapchete_eo.types import MergeMethod


def test_products_to_np_array(s2_stac_item, test_tile):
    assets = ["red", "green", "blue"]
    arr = products_to_np_array(
        products=[EOProduct.from_stac_item(s2_stac_item)],
        assets=assets,
        grid=test_tile,
        nodatavals=[0, 0, 0],
    )
    assert isinstance(arr, ma.MaskedArray)
    assert arr.any()
    assert not arr.mask.all()


def test_products_to_np_array_eo_bands(s2_stac_item, test_tile):
    eo_bands = ["red", "green", "blue"]
    arr = products_to_np_array(
        products=[EOProduct.from_stac_item(s2_stac_item)],
        eo_bands=eo_bands,
        grid=test_tile,
        nodatavals=[0, 0, 0],
    )
    assert isinstance(arr, ma.MaskedArray)
    assert arr.any()
    assert not arr.mask.all()


def test_products_to_np_array_merge_date(s2_stac_items, test_tile):
    eo_bands = ["red", "green", "blue"]
    arr = products_to_np_array(
        products=[EOProduct.from_stac_item(item) for item in s2_stac_items],
        eo_bands=eo_bands,
        grid=test_tile,
        merge_products_by="date",
    )
    assert isinstance(arr, ma.MaskedArray)
    assert arr.any()
    assert not arr.mask.all()
    assert arr.shape[0] == 2


@pytest.mark.parametrize(
    "merge_method",
    [MergeMethod.first, MergeMethod.average],
)
def test_products_to_np_array_merge_datastrip_id(
    s2_stac_items, test_tile, merge_method
):
    eo_bands = ["red", "green", "blue"]
    arr = products_to_np_array(
        products=[EOProduct.from_stac_item(item) for item in s2_stac_items],
        eo_bands=eo_bands,
        grid=test_tile,
        merge_products_by="s2:datastrip_id",
        merge_method=merge_method,
    )
    assert isinstance(arr, ma.MaskedArray)
    assert arr.any()
    assert not arr.mask.all()
    assert arr.shape[0] == 2
