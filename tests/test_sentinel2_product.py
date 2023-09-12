import numpy.ma as ma
from mapchete.io.vector import reproject_geometry
from mapchete.path import MPath
from mapchete.tile import BufferedTilePyramid
from mapchete.types import Bounds
from rasterio.crs import CRS

from mapchete_eo.platforms.sentinel2.config import BRDFConfig, CacheConfig
from mapchete_eo.platforms.sentinel2.product import S2Product


def test_product(s2_stac_item):
    product = S2Product(s2_stac_item)
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


def test_product_read_cloud_mask(s2_stac_item):
    product = S2Product(s2_stac_item)
    cloud_mask = product.read_cloud_mask()
    assert not isinstance(cloud_mask.data, ma.MaskedArray)
    assert cloud_mask.data.any()
    assert not cloud_mask.data.all()


def _get_product_tile(product):
    tp = BufferedTilePyramid("geodetic")
    centroid = reproject_geometry(product, product.crs, tp.crs).centroid
    return tp.tile_from_xy(centroid.x, centroid.y, 13)


def test_product_read_cloud_mask_tile(s2_stac_item):
    product = S2Product(s2_stac_item)
    tile = _get_product_tile(product)
    cloud_mask = product.read_cloud_mask(tile=tile)
    assert not isinstance(cloud_mask.data, ma.MaskedArray)
    assert cloud_mask.data.any()
    assert not cloud_mask.data.all()


def test_product_read_snow_ice_mask(s2_stac_item):
    product = S2Product(s2_stac_item)
    snow_ice_mask = product.read_snow_ice_mask()
    assert not isinstance(snow_ice_mask.data, ma.MaskedArray)


def test_product_read_snow_ice_mask_tile(s2_stac_item):
    product = S2Product(s2_stac_item)
    tile = _get_product_tile(product)
    snow_ice_mask = product.read_snow_ice_mask(tile=tile)
    assert not isinstance(snow_ice_mask.data, ma.MaskedArray)
