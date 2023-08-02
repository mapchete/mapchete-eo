import pytest

from mapchete_eo.platforms.sentinel2.base import AWSL2ACOGv1


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
