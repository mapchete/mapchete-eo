import pystac
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


def test_write_static_catalog(e84_cog_catalog, tmp_path):
    output_path = e84_cog_catalog.write_static_catalog(output_path=str(tmp_path))
    cat = pystac.Catalog.from_file(output_path)
    assert len(list(cat.get_all_items())) == 6


def test_write_static_catalog_copy_assets(e84_cog_catalog, tmp_path):
    output_path = e84_cog_catalog.write_static_catalog(
        output_path=str(tmp_path),
        copy_assets=["metadata"],
    )
    cat = pystac.Catalog.from_file(output_path)
    assert len(list(cat.get_all_items())) == 6
    for item in cat.get_all_items():
        assert "http" not in item.assets["metadata"].href
