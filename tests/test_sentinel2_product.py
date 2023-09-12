import numpy as np
import numpy.ma as ma
import pytest
from mapchete.io.raster import ReferencedRaster
from mapchete.io.vector import reproject_geometry
from mapchete.path import MPath
from mapchete.tile import BufferedTilePyramid
from mapchete.types import Bounds
from rasterio.crs import CRS

from mapchete_eo.platforms.sentinel2.config import BRDFConfig, CacheConfig
from mapchete_eo.platforms.sentinel2.product import S2Product
from mapchete_eo.platforms.sentinel2.types import Resolution


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


def _get_product_tile(product):
    tp = BufferedTilePyramid("geodetic")
    centroid = reproject_geometry(product, product.crs, tp.crs).centroid
    return tp.tile_from_xy(centroid.x, centroid.y, 13)


def test_product_read_cloud_mask(s2_stac_item):
    product = S2Product(s2_stac_item)
    cloud_mask = product.read_cloud_mask()
    assert isinstance(cloud_mask, ReferencedRaster)
    assert not isinstance(cloud_mask.data, ma.MaskedArray)
    assert cloud_mask.data.any()
    assert not cloud_mask.data.all()
    assert cloud_mask.data.dtype == bool
    assert cloud_mask.data.ndim == 2


def test_product_read_cloud_mask_tile(s2_stac_item):
    product = S2Product(s2_stac_item)
    cloud_mask = product.read_cloud_mask(_get_product_tile(product))
    assert isinstance(cloud_mask, ReferencedRaster)
    assert not isinstance(cloud_mask.data, ma.MaskedArray)
    assert cloud_mask.data.any()
    assert not cloud_mask.data.all()
    assert cloud_mask.data.dtype == bool
    assert cloud_mask.data.ndim == 2


def test_product_read_snow_ice_mask(s2_stac_item):
    product = S2Product(s2_stac_item)
    snow_ice_mask = product.read_snow_ice_mask()
    assert isinstance(snow_ice_mask, ReferencedRaster)
    assert not isinstance(snow_ice_mask.data, ma.MaskedArray)
    assert snow_ice_mask.data.dtype == bool
    assert snow_ice_mask.data.ndim == 2


def test_product_read_snow_ice_mask_tile(s2_stac_item):
    product = S2Product(s2_stac_item)
    snow_ice_mask = product.read_snow_ice_mask(_get_product_tile(product))
    assert isinstance(snow_ice_mask, ReferencedRaster)
    assert not isinstance(snow_ice_mask.data, ma.MaskedArray)
    assert snow_ice_mask.data.dtype == bool
    assert snow_ice_mask.data.ndim == 2


def test_product_read_cloud_probability_mask(s2_stac_item):
    product = S2Product(s2_stac_item)
    cloud_probability_mask = product.read_cloud_probability_mask()
    assert isinstance(cloud_probability_mask, ReferencedRaster)
    assert not isinstance(cloud_probability_mask.data, ma.MaskedArray)
    assert cloud_probability_mask.data.dtype == np.uint8
    assert cloud_probability_mask.data.ndim == 2


def test_product_read_cloud_probability_mask_tile(s2_stac_item):
    product = S2Product(s2_stac_item)
    cloud_probability_mask = product.read_cloud_probability_mask(
        _get_product_tile(product)
    )
    assert isinstance(cloud_probability_mask, ReferencedRaster)
    assert not isinstance(cloud_probability_mask.data, ma.MaskedArray)
    assert cloud_probability_mask.data.dtype == np.uint8
    assert cloud_probability_mask.data.ndim == 2


def test_product_read_snow_probability_mask(s2_stac_item):
    product = S2Product(s2_stac_item)
    snow_probability_mask = product.read_snow_probability_mask()
    assert isinstance(snow_probability_mask, ReferencedRaster)
    assert not isinstance(snow_probability_mask.data, ma.MaskedArray)
    assert snow_probability_mask.data.dtype == np.uint8
    assert snow_probability_mask.data.ndim == 2


def test_product_read_snow_probability_mask_tile(s2_stac_item):
    product = S2Product(s2_stac_item)
    snow_probability_mask = product.read_snow_probability_mask(
        _get_product_tile(product)
    )
    assert isinstance(snow_probability_mask, ReferencedRaster)
    assert not isinstance(snow_probability_mask.data, ma.MaskedArray)
    assert snow_probability_mask.data.dtype == np.uint8
    assert snow_probability_mask.data.ndim == 2


def test_product_read_scl_mask(s2_stac_item):
    product = S2Product(s2_stac_item)
    scl_mask = product.read_scl_mask()
    assert isinstance(scl_mask, ReferencedRaster)
    assert isinstance(scl_mask.data, ma.MaskedArray)
    assert scl_mask.data.dtype == np.uint8
    assert scl_mask.data.ndim == 2


def test_product_read_scl_mask_tile(s2_stac_item):
    product = S2Product(s2_stac_item)
    scl_mask = product.read_scl_mask(_get_product_tile(product))
    assert isinstance(scl_mask, ReferencedRaster)
    assert isinstance(scl_mask.data, ma.MaskedArray)
    assert scl_mask.data.dtype == np.uint8
    assert scl_mask.data.ndim == 2


def test_footprint_nodata_mask(s2_stac_item_half_footprint):
    product = S2Product(s2_stac_item_half_footprint)
    footprint_nodata_mask = product.footprint_nodata_mask()
    assert isinstance(footprint_nodata_mask, ReferencedRaster)
    assert not isinstance(footprint_nodata_mask.data, ma.MaskedArray)
    assert footprint_nodata_mask.data.any()
    assert not footprint_nodata_mask.data.all()
    assert footprint_nodata_mask.data.dtype == bool
    assert footprint_nodata_mask.data.ndim == 2


def test_footprint_nodata_mask_tile(s2_stac_item_half_footprint):
    product = S2Product(s2_stac_item_half_footprint)
    footprint_nodata_mask = product.footprint_nodata_mask(_get_product_tile(product))
    assert isinstance(footprint_nodata_mask, ReferencedRaster)
    assert not isinstance(footprint_nodata_mask.data, ma.MaskedArray)
    assert footprint_nodata_mask.data.all()
    assert footprint_nodata_mask.data.dtype == bool
    assert footprint_nodata_mask.data.ndim == 2


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(cloud=True),
        dict(snow_ice=True),
        dict(cloud_probability=True),
        dict(snow_probability=True),
        dict(scl=True),
    ],
)
def test_get_mask(s2_stac_item_half_footprint, kwargs):
    product = S2Product(s2_stac_item_half_footprint)
    mask = product.get_mask(Resolution["120m"], **kwargs)
    assert isinstance(mask, ReferencedRaster)
    assert not isinstance(mask.data, ma.MaskedArray)
    assert mask.data.any()
    assert mask.data.dtype == bool
    assert mask.data.ndim == 2
