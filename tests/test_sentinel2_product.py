import numpy as np
import numpy.ma as ma
import pytest
import xarray as xr
from mapchete.io.raster import ReferencedRaster
from mapchete.io.vector import reproject_geometry
from mapchete.path import MPath
from mapchete.tile import BufferedTilePyramid
from mapchete.types import Bounds
from pytest_lazyfixture import lazy_fixture
from rasterio.crs import CRS

from mapchete_eo.exceptions import (
    CorruptedProduct,
    EmptyProductException,
    EmptyStackException,
)
from mapchete_eo.io import read_levelled_cube_to_np_array, read_levelled_cube_to_xarray
from mapchete_eo.io.items import item_fix_footprint
from mapchete_eo.platforms.sentinel2.config import (
    BRDFConfig,
    BRDFModels,
    BRDFSCLClassConfig,
    CacheConfig,
    MaskConfig,
)
from mapchete_eo.platforms.sentinel2.product import S2Product
from mapchete_eo.platforms.sentinel2.types import (
    CloudType,
    Resolution,
    SceneClassification,
)


@pytest.mark.remote
@pytest.mark.parametrize(
    "item",
    [
        lazy_fixture("s2_stac_item"),
    ],
)
def test_product(item):
    product = S2Product(item)
    assert product.item
    assert product.metadata
    assert product.cache is None
    assert isinstance(product.bounds, Bounds)
    assert isinstance(product.crs, CRS)


@pytest.mark.remote
@pytest.mark.parametrize(
    "item",
    [
        lazy_fixture("stac_item_sentinel2_jp2_local"),
        lazy_fixture("stac_item_pb0300"),
        lazy_fixture("stac_item_pb0301"),
        lazy_fixture("stac_item_pb0400"),
        lazy_fixture("stac_item_pb0400_offset"),
        lazy_fixture("stac_item_pb0509"),
        lazy_fixture("stac_item_sentinel2_jp2"),
    ],
)
def test_product_remote(item):
    test_product(item)


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


def test_remote_product_asset_cache(s2_remote_stac_item, tmpdir):
    product = S2Product(
        s2_remote_stac_item,
        cache_config=CacheConfig(path=MPath.from_inp(tmpdir), assets=["coastal"]),
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
    path = product.cache.path.ls()[0]
    assert "B02" in str(path)


def _get_product_tile(product, metatiling=1):
    tp = BufferedTilePyramid("geodetic", metatiling=metatiling)
    centroid = reproject_geometry(product, product.crs, tp.crs).centroid
    return tp.tile_from_xy(centroid.x, centroid.y, 13)


def test_product_read_cloud_mask(s2_stac_item):
    product = S2Product(s2_stac_item)
    cloud_mask = product.read_l1c_cloud_mask()
    assert isinstance(cloud_mask, ReferencedRaster)
    assert not isinstance(cloud_mask.data, ma.MaskedArray)
    assert cloud_mask.data.any()
    assert not cloud_mask.data.all()
    assert cloud_mask.data.dtype == bool
    assert cloud_mask.data.ndim == 2


def test_product_read_cloud_mask_tile(s2_stac_item):
    product = S2Product(s2_stac_item)
    cloud_mask = product.read_l1c_cloud_mask(_get_product_tile(product))
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


@pytest.mark.remote
@pytest.mark.parametrize(
    "cached_read",
    [True, False],
)
def test_product_read_scl_remote(s2_l2a_earthsearch_remote_item, cached_read):
    product = S2Product(s2_l2a_earthsearch_remote_item)
    scl = product.read_scl(cached_read=cached_read)
    assert isinstance(scl, ReferencedRaster)
    assert isinstance(scl.data, ma.MaskedArray)
    assert scl.data.dtype == np.uint8
    assert scl.data.ndim == 2


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
    "item",
    [
        lazy_fixture("antimeridian_item1"),
        lazy_fixture("antimeridian_item2"),
        lazy_fixture("antimeridian_item3"),
        lazy_fixture("antimeridian_item4"),
    ],
)
def test_footprint_nodata_mask_tile_antimeridian(item):
    product = S2Product(item_fix_footprint(item))
    footprint_nodata_mask = product.footprint_nodata_mask(
        grid=BufferedTilePyramid("geodetic", metatiling=4).tile(13, 170, 0),
        buffer_m=-500,
    )
    assert isinstance(footprint_nodata_mask, ReferencedRaster)
    assert not isinstance(footprint_nodata_mask.data, ma.MaskedArray)
    assert footprint_nodata_mask.data.any()
    assert footprint_nodata_mask.data.dtype == bool
    assert footprint_nodata_mask.data.ndim == 2


@pytest.mark.parametrize(
    "mask_config",
    [
        MaskConfig(l1c_cloud_type=CloudType.all),
        MaskConfig(snow_ice=True),
        MaskConfig(scl_classes=[SceneClassification.vegetation]),
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
            cloud_probability_threshold=10,
            snow_probability_threshold=10,
            scl_classes=[
                SceneClassification.vegetation,
            ],
        ),
    )

    assert isinstance(masked, xr.Dataset)
    for asset in assets:
        assert masked[asset].any()
        assert (unmasked[asset] != masked[asset]).any()


def test_read_brdf(s2_stac_item_half_footprint):
    assets = ["red", "green", "blue"]
    product = S2Product(s2_stac_item_half_footprint)
    tile = _get_product_tile(product, metatiling=2)

    uncorrected = product.read(assets=assets, grid=tile)
    corrected = product.read(
        assets=assets,
        grid=tile,
        brdf_config=BRDFConfig(bands=assets),
    )

    assert isinstance(corrected, xr.Dataset)
    for asset in assets:
        assert corrected[asset].any()
        assert (uncorrected[asset] != corrected[asset]).any()


@pytest.mark.parametrize("correction_weight", (0.9, 1.1))
def test_read_brdf_correction_weight(s2_stac_item_half_footprint, correction_weight):
    assets = ["red", "green", "blue"]
    product = S2Product(s2_stac_item_half_footprint)
    tile = _get_product_tile(product, metatiling=2)

    corrected = product.read(
        assets=assets, grid=tile, brdf_config=BRDFConfig(bands=assets)
    )
    weighted_corrected = product.read(
        assets=assets,
        grid=tile,
        brdf_config=BRDFConfig(bands=assets, correction_weight=correction_weight),
    )

    assert isinstance(weighted_corrected, xr.Dataset)
    for asset in assets:
        assert weighted_corrected[asset].any()
        assert (corrected[asset] != weighted_corrected[asset]).any()
        if correction_weight < 1:
            assert weighted_corrected[asset].data.mean() > corrected[asset].data.mean()
        else:
            assert weighted_corrected[asset].data.mean() < corrected[asset].data.mean()


def test_read_brdf_scl_classes(s2_stac_item_half_footprint):
    """Default will be corrected, SCL classes won't."""
    assets = ["red"]
    product = S2Product(s2_stac_item_half_footprint)
    tile = _get_product_tile(product, metatiling=2)

    scl = product.read_scl(grid=tile).data
    available_scl_classes = [SceneClassification(i) for i in np.unique(scl)]
    # for each available class, activate/deactivate BRDF correction and compare with rest of image
    uncorrected = product.read_np_array(assets=assets, grid=tile)
    for scl_class in available_scl_classes:
        corrected = product.read_np_array(
            assets=assets,
            grid=tile,
            brdf_config=BRDFConfig(
                bands=assets,
                scl_specific_configurations=[
                    BRDFSCLClassConfig(model=BRDFModels.none, scl_classes=[scl_class])
                ],
            ),
        )
        scl_class_mask = np.where(scl == scl_class.value, True, False)
        for corrected_band, uncorrected_band in zip(corrected, uncorrected):
            # there should be some pixels not affected by correction
            assert np.where(corrected_band == uncorrected_band, True, False).any()
            # make sure pixel were not corrected for SCL class
            assert (
                uncorrected_band[scl_class_mask] == corrected_band[scl_class_mask]
            ).all()
            # make sure all other pixels were corrected
            assert (
                uncorrected_band[~scl_class_mask] != corrected_band[~scl_class_mask]
            ).all()


def test_read_brdf_scl_classes_inversed(s2_stac_item_half_footprint):
    """Default won't be corrected, SCL classes will."""
    assets = ["red"]
    product = S2Product(s2_stac_item_half_footprint)
    tile = _get_product_tile(product, metatiling=2)

    scl = product.read_scl(grid=tile).data
    available_scl_classes = [SceneClassification(i) for i in np.unique(scl)]
    # for each available class, activate/deactivate BRDF correction and compare with rest of image
    uncorrected = product.read_np_array(assets=assets, grid=tile)
    for scl_class in available_scl_classes:
        corrected = product.read_np_array(
            assets=assets,
            grid=tile,
            brdf_config=BRDFConfig(
                bands=assets,
                scl_specific_configurations=[
                    BRDFSCLClassConfig(model=BRDFModels.HLS, scl_classes=[scl_class])
                ],
                model=BRDFModels.none,
            ),
        )
        scl_class_mask = np.where(scl == scl_class.value, True, False)
        for corrected_band, uncorrected_band in zip(corrected, uncorrected):
            # there should be some pixels not affected by correction
            assert np.where(corrected_band == uncorrected_band, True, False).any()
            # make sure pixel were corrected for SCL class
            assert (
                uncorrected_band[scl_class_mask] != corrected_band[scl_class_mask]
            ).all()
            # make sure all other pixels were not corrected
            assert (
                uncorrected_band[~scl_class_mask] == corrected_band[~scl_class_mask]
            ).all()


@pytest.mark.remote
def test_read_broken_product(stac_item_missing_detector_footprints):
    assets = ["blue"]
    product = S2Product(stac_item_missing_detector_footprints)
    tile = _get_product_tile(product, metatiling=2)
    with pytest.raises(CorruptedProduct):
        product.read(assets=assets, grid=tile, brdf_config=BRDFConfig(bands=assets))


def test_read_empty_raise(s2_stac_item_half_footprint):
    assets = ["red"]
    product = S2Product(s2_stac_item_half_footprint)
    tile = BufferedTilePyramid("geodetic").tile(13, 0, 0)

    with pytest.raises(EmptyProductException):
        product.read(assets=assets, grid=tile)


def test_read_empty(s2_stac_item_half_footprint):
    assets = ["red"]
    product = S2Product(s2_stac_item_half_footprint)
    tile = BufferedTilePyramid("geodetic").tile(13, 0, 0)

    xarr = product.read(assets=assets, grid=tile, raise_empty=False)
    assert isinstance(xarr, xr.Dataset)


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
            l1c_cloud_type=CloudType.all,
            snow_ice=True,
            cloud_probability_threshold=50,
            snow_probability_threshold=50,
            scl_classes=[
                SceneClassification.vegetation,
                SceneClassification.thin_cirrus,
            ],
        ),
    )
    assert rgb_unmasked.mask.sum() < rgb.mask.sum()


@pytest.mark.parametrize(
    "item",
    [
        lazy_fixture("s2_stac_item"),
    ],
)
def test_read_np_brdf(item):
    assets = ["red", "green", "blue"]
    product = S2Product(item)
    tile = _get_product_tile(product)
    rgb_uncorrected = product.read_np_array(
        assets=assets,
        grid=tile,
    )
    rgb_corrected = product.read_np_array(
        assets=assets, grid=tile, brdf_config=BRDFConfig(bands=assets)
    )
    assert (rgb_uncorrected != rgb_corrected).any()


@pytest.mark.skip(
    reason="This takes ~1 minute and consumes requester pays requests but should pass."
)
@pytest.mark.remote
@pytest.mark.parametrize(
    "item",
    [
        lazy_fixture("stac_item_sentinel2_jp2"),
    ],
)
def test_read_np_brdf_remote(item):
    test_read_np_brdf(item)


def test_read_np_empty_raise(s2_stac_item_half_footprint):
    assets = ["red"]
    product = S2Product(s2_stac_item_half_footprint)
    tile = BufferedTilePyramid("geodetic").tile(13, 0, 0)

    with pytest.raises(EmptyProductException):
        product.read_np_array(assets=assets, grid=tile)


def test_read_np_empty(s2_stac_item_half_footprint):
    assets = ["red"]
    product = S2Product(s2_stac_item_half_footprint)
    tile = BufferedTilePyramid("geodetic").tile(13, 0, 0)

    arr = product.read_np_array(assets=assets, grid=tile, raise_empty=False)
    assert isinstance(arr, ma.MaskedArray)
    assert arr.mask.all()


def test_read_levelled_cube_xarray(s2_stac_items, test_tile):
    assets = ["red"]
    target_height = 5
    xarr = read_levelled_cube_to_xarray(
        products=[S2Product.from_stac_item(item) for item in s2_stac_items],
        target_height=target_height,
        assets=assets,
        grid=test_tile,
        merge_products_by="s2:datastrip_id",
        product_read_kwargs=dict(
            mask_config=MaskConfig(
                l1c_cloud_type=CloudType.all,
                cloud_probability_threshold=50,
            )
        ),
    )
    assert isinstance(xarr, xr.Dataset)


def test_read_levelled_cube_np_array(s2_stac_items, test_tile):
    assets = ["red"]
    target_height = 5
    arr = read_levelled_cube_to_np_array(
        products=[S2Product.from_stac_item(item) for item in s2_stac_items],
        target_height=target_height,
        assets=assets,
        grid=test_tile,
        merge_products_by="s2:datastrip_id",
        product_read_kwargs=dict(
            mask_config=MaskConfig(
                l1c_cloud_type=CloudType.all,
                cloud_probability_threshold=50,
            )
        ),
    )
    assert isinstance(arr, ma.MaskedArray)
    assert arr.any()
    assert not arr.mask.all()
    assert arr.shape[0] == target_height

    # not much a better way of testing it than to make sure, cube is filled from the bottom
    layers = list(range(target_height))
    for lower, higher in zip(layers[:-1], layers[1:]):
        assert arr[lower].mask.sum() <= arr[higher].mask.sum()


@pytest.mark.remote
def test_read_levelled_cube_broken_slice(stac_item_missing_detector_footprints):
    assets = ["blue"]
    target_height = 5
    product = S2Product.from_stac_item(stac_item_missing_detector_footprints)
    # stack will be empty because the only slice is broken
    with pytest.raises(EmptyStackException):
        read_levelled_cube_to_np_array(
            products=[product],
            target_height=target_height,
            assets=assets,
            grid=_get_product_tile(product, metatiling=2),
            merge_products_by="s2:datastrip_id",
            product_read_kwargs=dict(brdf_config=BRDFConfig(bands=assets)),
        )


@pytest.mark.remote
@pytest.mark.parametrize(
    "asset",
    ["coastal"],
    # "red" asset fails because the local version has lower resolution and lossy compressed
)
def test_read_apply_offset(asset, s2_stac_item, s2_stac_item_jp2):
    assets = [asset]
    cog_product = S2Product(s2_stac_item)
    jp2_product = S2Product(s2_stac_item_jp2)
    tile = _get_product_tile(cog_product)

    # (1) read array from COG archive where offset was already applied by the provider
    cog = cog_product.read_np_array(assets=assets, grid=tile)

    # (2) read array from JP2 archive where offset was not provided but apply it ourselves
    jp2 = jp2_product.read_np_array(assets=assets, grid=tile)

    # --> 1 and 2 should be identical
    assert (cog == jp2).all()

    # (3) read array from JP2 archive but deactivate offset appliance
    # --> 1 and 3 should differ by 1000
    jp2_unapplied = jp2_product.read_np_array(
        assets=assets, grid=tile, apply_offset=False
    )
    assert (jp2_unapplied != cog).all()
    assert (jp2_unapplied - 1000 == cog).all()
