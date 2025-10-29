import pytest

from mapchete_eo.types import TimeRange
from mapchete_eo.platforms.sentinel2.sources_mappers import KNOWN_SOURCES
from mapchete_eo.platforms.sentinel2.source import Sentinel2Source


@pytest.mark.parametrize("source_id", list(KNOWN_SOURCES.keys()))
def test_known_source(source_id):
    source = Sentinel2Source(stac_catalog=source_id)
    assert source
    for item in source.search(
        time=TimeRange(start="2025-01-01", end="2025-01-10"), bounds=[16, 46, 17, 47]
    ):
        assert item
        break
    else:
        raise ValueError("no products found!")
