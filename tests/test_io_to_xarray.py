import pytest
import xarray as xr

from mapchete_eo.io import products_to_xarray
from mapchete_eo.product import EOProduct


def test_products_to_xarray(s2_stac_item, test_tile):
    assets = ["red", "green", "blue"]
    ds = products_to_xarray(
        products=[EOProduct.from_stac_item(s2_stac_item)],
        assets=assets,
        grid=test_tile,
        nodatavals=[0, 0, 0],
    )
    assert isinstance(ds, xr.Dataset)
    assert set(ds.data_vars) == set([s2_stac_item.id])
    assert ds.any()


def test_products_to_xarray_eo_bands(s2_stac_item, test_tile):
    eo_bands = ["red", "green", "blue"]
    ds = products_to_xarray(
        products=[EOProduct.from_stac_item(s2_stac_item)],
        eo_bands=eo_bands,
        grid=test_tile,
        nodatavals=[0, 0, 0],
    )
    assert isinstance(ds, xr.Dataset)
    assert set(ds.data_vars) == set([s2_stac_item.id])
    assert ds.any()


def test_products_to_xarray_merge_date(s2_stac_items, test_tile):
    eo_bands = ["red", "green", "blue"]
    ds = products_to_xarray(
        products=[EOProduct.from_stac_item(item) for item in s2_stac_items],
        eo_bands=eo_bands,
        grid=test_tile,
        merge_products_by="date",
    )
    assert len(ds.data_vars) >= 2
    assert isinstance(ds, xr.Dataset)


@pytest.mark.parametrize(
    "merge_method",
    ["first", "average"],
)
def test_products_to_xarray_merge_datastrip_id(s2_stac_items, test_tile, merge_method):
    eo_bands = ["red", "green", "blue"]
    ds = products_to_xarray(
        products=[EOProduct.from_stac_item(item) for item in s2_stac_items],
        eo_bands=eo_bands,
        grid=test_tile,
        merge_products_by="s2:datastrip_id",
        merge_method=merge_method,
    )
    assert len(ds) >= 2
    assert isinstance(ds, xr.Dataset)
    assert "s2:datastrip_id" in ds.coords
