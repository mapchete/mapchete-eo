import pystac
import pytest
import rasterio
from mapchete.io import fs_from_path, path_exists
from mapchete.io.vector import IndexedFeatures

from mapchete_eo.search import STACStaticCatalog


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


@pytest.mark.webtest
def test_write_static_catalog(e84_cog_catalog, tmp_path):
    output_path = e84_cog_catalog.write_static_catalog(output_path=str(tmp_path))
    cat = pystac.Catalog.from_file(output_path)
    assert len(list(cat.get_all_items())) == 18


@pytest.mark.webtest
def test_write_static_catalog_copy_assets(e84_cog_catalog_short, tmp_path):
    output_path = e84_cog_catalog_short.write_static_catalog(
        output_path=str(tmp_path),
        assets=["metadata"],
    )
    cat = pystac.Catalog.from_file(output_path)
    assert len(list(cat.get_all_items())) == 1
    for item in cat.get_all_items():
        assert item.assets["metadata"].href == "./metadata.xml"
        item.make_asset_hrefs_absolute()
        assert path_exists(item.assets["metadata"].href)


@pytest.mark.webtest
def test_write_static_catalog_copy_assets_relative_output_path(e84_cog_catalog_short):
    tmp_path = "tmp_static_catalog"
    try:
        output_path = e84_cog_catalog_short.write_static_catalog(
            output_path=str(tmp_path),
            assets=["metadata"],
        )
        cat = pystac.Catalog.from_file(output_path)
        assert len(list(cat.get_all_items())) == 1
        for item in cat.get_all_items():
            assert item.assets["metadata"].href == "./metadata.xml"
            item.make_asset_hrefs_absolute()
            assert path_exists(item.assets["metadata"].href)
    finally:
        try:
            fs_from_path(tmp_path).rm(tmp_path, recursive=True)
        except FileNotFoundError:
            pass


@pytest.mark.webtest
def test_write_static_catalog_convert_assets(e84_cog_catalog_short, tmp_path):
    asset = "B01"
    resolution = 120.0
    output_path = e84_cog_catalog_short.write_static_catalog(
        output_path=str(tmp_path),
        assets=[asset],
        assets_dst_resolution=120,
    )
    cat = pystac.Catalog.from_file(output_path)
    assert len(list(cat.get_all_items())) == 1
    for item in cat.get_all_items():
        assert "http" not in item.assets[asset].href
        item.make_asset_hrefs_absolute()
        with rasterio.open(item.assets[asset].href) as src:
            assert src.meta["transform"][0] == resolution
            assert src.read(masked=True).any()
