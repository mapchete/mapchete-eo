from mapchete.io.vector import IndexedFeatures


def test_e84_cog_catalog_search_items(e84_cog_catalog):
    assert len(e84_cog_catalog.items) > 0


def test_e84_cog_catalog_search_items_type(e84_cog_catalog):
    assert isinstance(e84_cog_catalog.items, IndexedFeatures)


def test_e84_cog_catalog_eo_bands(e84_cog_catalog):
    assert len(e84_cog_catalog.eo_bands) > 0
