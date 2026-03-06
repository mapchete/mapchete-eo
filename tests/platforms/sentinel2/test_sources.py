import pytest

from mapchete_eo.io.path import asset_mpath
from mapchete_eo.types import TimeRange
from mapchete_eo.platforms.sentinel2.source import Sentinel2Source


@pytest.mark.remote
@pytest.mark.parametrize("collection", ["EarthSearch", "EarthSearch_legacy"])
def test_known_sources(collection):
    source = Sentinel2Source(collection=collection)
    assert source
    for item in source.search(
        time=TimeRange(start="2025-01-01", end="2025-01-10"), bounds=[16, 46, 17, 47]
    ):
        assert item

        # assert asset paths exist
        for asset in ["red", "green", "blue", "nir"]:
            assert asset_mpath(item, asset).exists()

        # assert S2Metadata object can be created and QI bands are there
        s2metadata = source.get_s2metadata_mapper()(item)
        assert s2metadata.datastrip_id
        for asset in s2metadata.assets.values():
            assert asset.exists()

        # we only need the first item to be checked
        break
    else:
        raise ValueError("no products found!")


@pytest.mark.remote
@pytest.mark.use_cdse_test_env
@pytest.mark.parametrize("collection", ["CDSE"])
@pytest.mark.xfail(reason="CDSE endpoint is flaky")
def test_known_sources_cdse(collection, sentinel2_cdse_mapchete):
    # using sentinel2_cdse_mapchete fixture to trigger CDSE endpoint check
    test_known_sources(collection)
