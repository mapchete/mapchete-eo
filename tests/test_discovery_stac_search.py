from mapchete.io.vector import IndexedFeatures


def test_s2_search_items(stac_search_catalog):
    assert len(stac_search_catalog.items) > 0


def test_s2_search_items_type(stac_search_catalog):
    assert isinstance(stac_search_catalog.items, IndexedFeatures)


def stac_s2_eo_bands(stac_search_catalog):
    assert len(stac_search_catalog.eo_bands) > 0
