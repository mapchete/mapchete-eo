from mapchete.io.vector import IndexedFeatures

from mapchete_eo.discovery import STACStaticCatalog


def test_pf_sr_items(pf_sr_stac_collection):
    catalog = STACStaticCatalog(pf_sr_stac_collection)
    assert len(catalog.items) > 0


def test_pf_sr_items_type(pf_sr_stac_collection):
    catalog = STACStaticCatalog(pf_sr_stac_collection)
    assert isinstance(catalog.items, IndexedFeatures)


def test_pf_sr_eo_bands(pf_sr_stac_collection):
    catalog = STACStaticCatalog(pf_sr_stac_collection)
    assert len(catalog.eo_bands) > 0


def test_pf_qa_items(pf_qa_stac_collection):
    catalog = STACStaticCatalog(pf_qa_stac_collection)
    assert len(catalog.items) > 0


def test_pf_qa_items_type(pf_qa_stac_collection):
    catalog = STACStaticCatalog(pf_qa_stac_collection)
    assert isinstance(catalog.items, IndexedFeatures)


def test_pf_qa_eo_bands(pf_qa_stac_collection):
    catalog = STACStaticCatalog(pf_qa_stac_collection)
    assert len(catalog.eo_bands) > 0
