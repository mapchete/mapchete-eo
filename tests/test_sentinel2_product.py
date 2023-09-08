import pytest
from mapchete.path import MPath
from mapchete.types import Bounds
from rasterio.crs import CRS

from mapchete_eo.platforms.sentinel2.config import BRDFConfig, CacheConfig
from mapchete_eo.platforms.sentinel2.product import S2Product


def test_product(s2_stac_item):
    product = S2Product(
        s2_stac_item,
    )
    assert product.item
    assert product.metadata
    assert product.cache is None
    assert isinstance(product.bounds, Bounds)
    assert isinstance(product.crs, CRS)


def test_product_asset_cache(s2_stac_item, tmpdir):
    product = S2Product(
        s2_stac_item,
        cache_config=CacheConfig(
            path=MPath.from_inp(tmpdir), assets=["granule_metadata"]
        ),
    )
    assert product.cache
    assert not product.cache.path.ls()
    product.cache_assets()
    assert product.cache.path.ls()


def test_product_brdf_cache(s2_stac_item, tmpdir):
    product = S2Product(
        s2_stac_item,
        cache_config=CacheConfig(
            path=MPath.from_inp(tmpdir), brdf=BRDFConfig(bands=["blue"])
        ),
    )
    assert product.cache
    assert not product.cache.path.ls()
    product.cache_brdf_grids()
    assert product.cache.path.ls()
