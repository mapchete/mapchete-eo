import pytest

from pystac import Item

from mapchete_eo.platforms.sentinel2.preconfigured_sources.item_mappers import (
    earthsearch_to_s2metadata,
)


@pytest.mark.parametrize(
    "item_url",
    [
        "https://earth-search.aws.element84.com/v1/collections/sentinel-2-c1-l2a/items/S2A_T33TWL_20250109T100401_L2A"
    ],
)
def test_earthsearch_to_s2metadata(item_url):
    s2metadata = earthsearch_to_s2metadata(Item.from_file(item_url))
    for asset in s2metadata.assets.values():
        assert asset.exists()
