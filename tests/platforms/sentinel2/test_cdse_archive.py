import pytest
from mapchete.tile import BufferedTilePyramid
from shapely.geometry import shape
from shapely.ops import unary_union

from mapchete_eo.io.path import asset_mpath
from mapchete_eo.platforms.sentinel2.archives import CDSEL2AJP2CSDE

from mapchete_eo.platforms.sentinel2.product import S2Product
from mapchete_eo.types import TimeRange


@pytest.mark.remote
@pytest.mark.set_cdse_test_env
@pytest.mark.parametrize(
    "archive_cls",
    [CDSEL2AJP2CSDE],
)
def test_s2_archives(archive_cls):
    time = TimeRange(start="2022-06-06", end="2022-06-06")
    bounds = [16, 46, 17, 47]
    archive = archive_cls(time=time, bounds=bounds)
    assert len(list(archive.items()))


@pytest.mark.remote
@pytest.mark.set_cdse_test_env
@pytest.mark.parametrize(
    "archive_cls",
    [CDSEL2AJP2CSDE],
)
def test_s2_archives_assets(archive_cls):
    assets = ["red", "green", "blue", "coastal", "nir"]
    time = TimeRange(start="2022-06-06", end="2022-06-06")
    bounds = [16, 46, 17, 47]
    archive = archive_cls(time=time, bounds=bounds)
    for item in archive.items():
        product = S2Product.from_stac_item(item)
        for band_location in product.eo_bands_to_band_location(assets):
            assert asset_mpath(item, band_location.asset_name).exists()


@pytest.mark.remote
@pytest.mark.set_cdse_test_env
@pytest.mark.parametrize(
    "archive_cls",
    [CDSEL2AJP2CSDE],
)
def test_s2_archives_multipolygon_search(archive_cls):
    pyramid = BufferedTilePyramid("geodetic")
    time = TimeRange(start="2022-06-06", end="2022-06-06")
    area = unary_union(
        [pyramid.tile_from_xy(16, 46, 13).bbox, pyramid.tile_from_xy(17, 47, 13).bbox]
    )
    archive = archive_cls(
        time=time,
        area=area,
    )
    items = list(archive.items())
    assert items
    for item in items:
        assert shape(item.geometry).intersects(area)
