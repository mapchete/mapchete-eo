import numpy as np
import numpy.ma as ma
import pytest
import xarray as xr
from mapchete.io.raster import ReferencedRaster
from mapchete.io.vector import reproject_geometry
from mapchete.path import MPath
from mapchete.tile import BufferedTilePyramid
from mapchete.types import Bounds
from rasterio.crs import CRS

from mapchete_eo.platforms.sentinel2.config import BRDFConfig, CacheConfig, MaskConfig
from mapchete_eo.platforms.sentinel2.product import S2Product
from mapchete_eo.platforms.sentinel2.types import Resolution, SceneClassification


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


def _get_product_tile(product, metatiling=1):
    tp = BufferedTilePyramid("geodetic", metatiling=metatiling)
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


def test_product_read_cloud_probability(s2_stac_item):
    product = S2Product(s2_stac_item)
    cloud_probability = product.read_cloud_probability()
    assert isinstance(cloud_probability, ReferencedRaster)
    assert not isinstance(cloud_probability.data, ma.MaskedArray)
    assert cloud_probability.data.dtype == np.uint8
    assert cloud_probability.data.ndim == 2


def test_product_read_cloud_probability_tile(s2_stac_item):
    product = S2Product(s2_stac_item)
    cloud_probability = product.read_cloud_probability(_get_product_tile(product))
    assert isinstance(cloud_probability, ReferencedRaster)
    assert not isinstance(cloud_probability.data, ma.MaskedArray)
    assert cloud_probability.data.dtype == np.uint8
    assert cloud_probability.data.ndim == 2


def test_product_read_snow_probability(s2_stac_item):
    product = S2Product(s2_stac_item)
    snow_probability = product.read_snow_probability()
    assert isinstance(snow_probability, ReferencedRaster)
    assert not isinstance(snow_probability.data, ma.MaskedArray)
    assert snow_probability.data.dtype == np.uint8
    assert snow_probability.data.ndim == 2


def test_product_read_snow_probability_tile(s2_stac_item):
    product = S2Product(s2_stac_item)
    snow_probability = product.read_snow_probability(_get_product_tile(product))
    assert isinstance(snow_probability, ReferencedRaster)
    assert not isinstance(snow_probability.data, ma.MaskedArray)
    assert snow_probability.data.dtype == np.uint8
    assert snow_probability.data.ndim == 2


def test_product_read_scl(s2_stac_item):
    product = S2Product(s2_stac_item)
    scl = product.read_scl()
    assert isinstance(scl, ReferencedRaster)
    assert isinstance(scl.data, ma.MaskedArray)
    assert scl.data.dtype == np.uint8
    assert scl.data.ndim == 2


def test_product_read_scl_tile(s2_stac_item):
    product = S2Product(s2_stac_item)
    scl = product.read_scl(_get_product_tile(product))
    assert isinstance(scl, ReferencedRaster)
    assert isinstance(scl.data, ma.MaskedArray)
    assert scl.data.dtype == np.uint8
    assert scl.data.ndim == 2


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
    assert not footprint_nodata_mask.data.any()
    assert footprint_nodata_mask.data.dtype == bool
    assert footprint_nodata_mask.data.ndim == 2


@pytest.mark.parametrize(
    "mask_config",
    [
        MaskConfig(cloud=True),
        MaskConfig(snow_ice=True),
        MaskConfig(cloud_probability=True),
        MaskConfig(snow_probability=True),
        MaskConfig(scl=True),
    ],
)
def test_get_mask(s2_stac_item_half_footprint, mask_config):
    product = S2Product(s2_stac_item_half_footprint)
    mask = product.get_mask(Resolution["120m"], mask_config)
    assert isinstance(mask, ReferencedRaster)
    assert not isinstance(mask.data, ma.MaskedArray)
    assert mask.data.any()
    assert mask.data.dtype == bool
    assert mask.data.ndim == 2


def test_read(s2_stac_item_half_footprint):
    assets = ["red", "green", "blue"]
    product = S2Product(s2_stac_item_half_footprint)

    rgb = product.read(assets=assets, grid=_get_product_tile(product))

    assert isinstance(rgb, xr.Dataset)
    for asset in assets:
        assert asset in rgb.data_vars


def test_read_masked(s2_stac_item_half_footprint):
    assets = ["red", "green", "blue"]
    product = S2Product(s2_stac_item_half_footprint)
    tile = _get_product_tile(product, metatiling=2)

    unmasked = product.read(assets=assets, grid=tile)
    masked = product.read(
        assets=assets,
        grid=tile,
        mask_config=MaskConfig(
            footprint=True,
            snow_ice=True,
            cloud_probability=True,
            cloud_probability_threshold=10,
            snow_probability=True,
            snow_probability_threshold=10,
            scl=True,
            scl_classes=[
                SceneClassification.vegetation,
            ],
        ),
    )

    assert isinstance(masked, xr.Dataset)
    for asset in assets:
        assert masked[asset].any()
        assert (unmasked[asset] != masked[asset]).any()


def test_read_np(s2_stac_item_half_footprint):
    assets = ["red", "green", "blue"]
    product = S2Product(s2_stac_item_half_footprint)
    tile = _get_product_tile(product)
    rgb = product.read_np_array(assets=assets, grid=tile)
    assert isinstance(rgb, ma.MaskedArray)
    assert rgb.shape == (len(assets), tile.height, tile.width)
    assert rgb.dtype == np.uint16


def test_read_np_masked(s2_stac_item):
    assets = ["red", "green", "blue"]
    product = S2Product(s2_stac_item)
    tile = _get_product_tile(product)
    rgb_unmasked = product.read_np_array(
        assets=assets,
        grid=tile,
    )
    rgb = product.read_np_array(
        assets=assets,
        grid=tile,
        mask_config=MaskConfig(
            footprint=True,
            cloud=True,
            snow_ice=True,
            cloud_probability=True,
            cloud_probability_threshold=50,
            snow_probability=True,
            snow_probability_threshold=50,
            scl=True,
            scl_classes=[
                SceneClassification.vegetation,
                SceneClassification.thin_cirrus,
            ],
        ),
    )
    assert rgb_unmasked.mask.sum() < rgb.mask.sum()
