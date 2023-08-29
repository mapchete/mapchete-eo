import pytest
from mapchete.io.vector import IndexedFeatures


@pytest.mark.remote
def test_e84_cog_catalog_search_items(e84_cog_catalog):
    assert len(e84_cog_catalog.items) > 0


@pytest.mark.remote
def test_e84_cog_catalog_search_items_type(e84_cog_catalog):
    assert isinstance(e84_cog_catalog.items, IndexedFeatures)


@pytest.mark.remote
def test_e84_cog_catalog_eo_bands(e84_cog_catalog):
    assert len(e84_cog_catalog.eo_bands) > 0
