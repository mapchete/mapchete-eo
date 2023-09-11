import pytest
import rasterio
from mapchete.io import copy
from mapchete.path import MPath

from mapchete_eo.io.assets import (
    asset_mpath,
    convert_asset,
    convert_raster,
    copy_asset,
    eo_bands_to_assets_indexes,
    get_assets,
    get_metadata_assets,
    should_be_converted,
)
from mapchete_eo.io.profiles import COGDeflateProfile, JP2LossyProfile
from mapchete_eo.platforms.sentinel2.metadata_parser import S2Metadata


def test_s2_eo_bands_to_assets_indexes(s2_stac_item):
    eo_bands = ["red", "green", "blue"]
    assets_indexes = eo_bands_to_assets_indexes(s2_stac_item, eo_bands)
    assert len(eo_bands) == len(assets_indexes)
    for eo_band, (asset, index) in zip(eo_bands, assets_indexes):
        assert eo_band == asset
        assert index == 1


def test_s2_eo_bands_to_assets_indexes_invalid_band(s2_stac_item):
    eo_bands = ["foo"]
    with pytest.raises(KeyError):
        eo_bands_to_assets_indexes(s2_stac_item, eo_bands)


# TODO:
# --> PF Elias:
# DataSet
# per band 1 DataArray
# each DataArray has 3 dimensions: time, x, y
def test_pf_eo_bands_to_assets_indexes(pf_sr_stac_item):
    eo_bands = ["B3", "B2", "B4"]
    assets_indexes = eo_bands_to_assets_indexes(pf_sr_stac_item, eo_bands)
    assert len(eo_bands) == len(assets_indexes)
    for band_index, (asset, index) in zip([1, 2, 4], assets_indexes):
        assert asset == "bands"
        assert band_index == index


def test_asset_mpath(s2_stac_item):
    assert isinstance(asset_mpath(s2_stac_item, "red"), MPath)


def test_asset_mpath_error(s2_stac_item):
    with pytest.raises(KeyError):
        asset_mpath(s2_stac_item, "foo")


def test_get_assets_copy(s2_stac_item, tmp_mpath):
    asset = "red"
    orig_meta = rasterio.open(s2_stac_item.assets[asset].href).meta
    item = get_assets(s2_stac_item, [asset], tmp_mpath)
    assert tmp_mpath.ls()
    copied_meta = rasterio.open(item.assets[asset].href).meta
    assert orig_meta == copied_meta


def test_get_assets_convert(s2_stac_item, tmp_mpath):
    asset = "red"
    orig_meta = rasterio.open(s2_stac_item.assets[asset].href).meta
    item = get_assets(s2_stac_item, [asset], tmp_mpath, resolution=60)
    assert tmp_mpath.ls()
    copied_meta = rasterio.open(item.assets[asset].href).meta
    assert orig_meta != copied_meta


def test_copy_asset(s2_stac_item, tmp_mpath):
    asset = "red"
    assert not tmp_mpath.ls()

    # copy asset the first time
    copy_asset(s2_stac_item, asset, tmp_mpath)
    assert tmp_mpath.ls()

    # raise error if overwrite is not activated
    with pytest.raises(IOError):
        copy_asset(s2_stac_item, asset, tmp_mpath, overwrite=False)

    # don't raise error if ignore flag is activated
    copy_asset(s2_stac_item, asset, tmp_mpath, ignore_if_exists=True)


def test_copy_asset_overwrite(s2_stac_item, tmp_mpath):
    asset = "red"
    assert not tmp_mpath.ls()

    # copy asset the first time
    src_path = MPath(s2_stac_item.assets[asset].href)
    copy(src_path, tmp_mpath / src_path.name)

    # also don't raise error if overwrite flag is activated
    copy_asset(s2_stac_item, asset, tmp_mpath, overwrite=True)


def test_convert_asset(s2_stac_item, tmp_mpath):
    asset = "red"
    assert not tmp_mpath.ls()

    # copy asset the first time
    convert_asset(s2_stac_item, asset, tmp_mpath)
    assert tmp_mpath.ls()

    # raise error if overwrite is not activated
    with pytest.raises(IOError):
        convert_asset(s2_stac_item, asset, tmp_mpath, overwrite=False)

    # don't raise error if ignore flag is activated
    convert_asset(s2_stac_item, asset, tmp_mpath, ignore_if_exists=True)

    # also don't raise error if overwrite flag is activated
    convert_asset(s2_stac_item, asset, tmp_mpath, overwrite=True)


def test_convert_asset_ignore_existing(s2_stac_item, tmp_mpath):
    asset = "red"
    assert not tmp_mpath.ls()

    # copy asset the first time
    convert_asset(s2_stac_item, asset, tmp_mpath)
    assert tmp_mpath.ls()

    # don't raise error if ignore flag is activated
    convert_asset(s2_stac_item, asset, tmp_mpath, ignore_if_exists=True)


def test_convert_asset_overwrite(s2_stac_item, tmp_mpath):
    asset = "red"
    assert not tmp_mpath.ls()

    # copy asset the first time
    src_path = MPath(s2_stac_item.assets[asset].href)
    copy(src_path, tmp_mpath / src_path.name)
    assert tmp_mpath.ls()

    # also don't raise error if overwrite flag is activated
    convert_asset(s2_stac_item, asset, tmp_mpath, overwrite=True)


def test_convert_raster_resolution(s2_stac_item, tmp_mpath):
    asset = "red"
    resolution = 20.0
    src_path = MPath.from_inp(s2_stac_item.assets[asset].href)
    dst_path = tmp_mpath / src_path.name
    convert_raster(src_path, dst_path, resolution=resolution)
    with rasterio.open(dst_path) as src:
        assert src.transform[0] == resolution


def test_convert_raster_profile(s2_stac_item, tmp_mpath):
    asset = "red"
    profile = COGDeflateProfile()
    src_path = MPath.from_inp(s2_stac_item.assets[asset].href)
    dst_path = tmp_mpath / src_path.name
    convert_raster(src_path, dst_path, profile=profile)
    with rasterio.open(dst_path) as src:
        for k, v in profile.items():
            if v == "COG":
                v = "GTiff"
            if isinstance(v, str):
                assert src.profile[k].lower() == v.lower()
            else:
                assert src.profile[k] == v


def test_get_metadata_assets(s2_stac_item, tmp_mpath):
    assert not tmp_mpath.ls()
    get_metadata_assets(s2_stac_item, tmp_mpath, metadata_parser_classes=(S2Metadata,))
    assert tmp_mpath.ls()


@pytest.mark.skip(reason="Converting all metadata assets takes too long.")
def test_get_metadata_assets_convert(s2_stac_item, tmp_mpath):
    resolution = 240.0
    assert not tmp_mpath.ls()
    get_metadata_assets(
        s2_stac_item,
        tmp_mpath,
        metadata_parser_classes=(S2Metadata,),
        resolution=resolution,
    )
    assert tmp_mpath.ls()
    for f in tmp_mpath.ls():
        if f.suffix == ".jp2":
            assert rasterio.open(f).transform[0] == resolution


@pytest.mark.parametrize(
    "kwargs,control",
    [
        (dict(resolution=120), False),
        (dict(), False),
        (dict(resolution=10), True),
        (dict(profile=COGDeflateProfile()), True),
        (dict(profile=JP2LossyProfile()), True),
        (dict(resolution=10, profile=COGDeflateProfile()), True),
    ],
)
def test_should_be_converted(s2_stac_item, kwargs, control):
    band = MPath(s2_stac_item.assets["red"].href)
    assert should_be_converted(band, **kwargs) == control
