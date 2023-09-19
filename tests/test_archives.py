import pytest
from mapchete.tile import BufferedTilePyramid
from shapely.ops import unary_union

from mapchete_eo.platforms.sentinel2.config import AWSL2ACOGv1


@pytest.mark.remote
@pytest.mark.parametrize(
    "archive_cls",
    [AWSL2ACOGv1],
)
def test_s2_archives(archive_cls):
    start_time = "2022-06-01"
    end_time = "2022-06-06"
    bounds = [16, 46, 17, 47]
    archive = archive_cls(start_time=start_time, end_time=end_time, bounds=bounds)
    assert len(archive.catalog.items)


@pytest.mark.remote
@pytest.mark.parametrize(
    "archive_cls",
    [AWSL2ACOGv1],
)
def test_s2_archives_multipolygon_search(archive_cls):
    pyramid = BufferedTilePyramid("geodetic")
    start_time = "2022-06-01"
    end_time = "2022-06-06"
    area = unary_union(
        [pyramid.tile_from_xy(16, 46, 13).bbox, pyramid.tile_from_xy(17, 47, 13).bbox]
    )
    archive = archive_cls(start_time=start_time, end_time=end_time, area=area)
    breakpoint()
    assert len(archive.catalog.items)
