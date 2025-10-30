import pytest

from mapchete_eo.io.path import asset_mpath
from mapchete_eo.types import TimeRange
from mapchete_eo.platforms.sentinel2.source import Sentinel2Source


@pytest.mark.remote
@pytest.mark.parametrize("source_id", ["EarthSearch", "EarthSearch_legacy"])
def test_known_sources(source_id):
    source = Sentinel2Source(stac_catalog=source_id)
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
@pytest.mark.parametrize("source_id", ["CSDE"])
def test_known_sources_cdse(source_id):
    test_known_sources(source_id)
