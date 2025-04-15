import pystac_client
import rasterio
from mapchete.io import fs_from_path, path_exists
from mapchete.io.raster import rasterio_open
from mapchete.io.vector import IndexedFeatures
from mapchete.path import MPath

from mapchete_eo.known_catalogs import EarthSearchV1S2L2A, AWSSearchCatalogS2L2A
from mapchete_eo.platforms.sentinel2 import S2Metadata
from mapchete_eo.platforms.sentinel2.types import Resolution
from mapchete_eo.search import STACStaticCatalog
from mapchete_eo.search.config import (
    StacSearchConfig,
    StacStaticConfig,
    UTMSearchConfig,
)
from mapchete_eo.types import TimeRange


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


def test_write_static_catalog(static_catalog_small, tmp_path):
    output_path = static_catalog_small.write_static_catalog(output_path=str(tmp_path))
    cat = pystac_client.Client.from_file(str(output_path))
    collections = list(cat.get_children())
    assert len(collections) == 1
    collection = collections[0]
    assert len(list(collection.get_items())) == 1


def test_write_static_catalog_copy_assets(static_catalog_small, tmp_path):
    output_path = static_catalog_small.write_static_catalog(
        output_path=str(tmp_path),
        assets=["granule_metadata"],
    )
    cat = pystac_client.Client.from_file(str(output_path))
    collections = list(cat.get_children())
    assert len(collections) == 1
    collection = collections[0]
    items = list(collection.get_items())
    assert len(items) == 1
    for item in items:
        assert item.assets["granule_metadata"].href == "./granule_metadata.xml"
        item.make_asset_hrefs_absolute()
        assert path_exists(item.assets["granule_metadata"].href)


def test_write_static_catalog_copy_assets_relative_output_path(static_catalog_small):
    tmp_path = "tmp_static_catalog"
    try:
        output_path = static_catalog_small.write_static_catalog(
            output_path=str(tmp_path),
            assets=["granule_metadata"],
        )
        cat = pystac_client.Client.from_file(str(output_path))
        collections = list(cat.get_children())
        assert len(collections) == 1
        collection = collections[0]
        items = list(collection.get_items())
        assert len(items) == 1
        for item in items:
            assert item.assets["granule_metadata"].href == "./granule_metadata.xml"
            item.make_asset_hrefs_absolute()
            assert path_exists(item.assets["granule_metadata"].href)
    finally:
        try:
            fs_from_path(tmp_path).rm(tmp_path, recursive=True)
        except FileNotFoundError:
            pass


def test_write_static_catalog_convert_assets(static_catalog_small, tmp_path):
    asset = "coastal"
    resolution = Resolution["120m"]
    output_path = static_catalog_small.write_static_catalog(
        output_path=str(tmp_path),
        assets=[asset],
        assets_dst_resolution=resolution.value,
    )
    cat = pystac_client.Client.from_file(str(output_path))
    collections = list(cat.get_children())
    assert len(collections) == 1
    collection = collections[0]
    items = list(collection.get_items())
    assert len(items) == 1
    for item in items:
        assert "http" not in item.assets[asset].href
        item.make_asset_hrefs_absolute()
        with rasterio.open(item.assets[asset].href) as src:
            assert src.meta["transform"][0] == resolution.value
            assert src.read(masked=True).any()


def test_write_static_catalog_metadata_assets(static_catalog_small, tmp_path):
    static_catalog_small.write_static_catalog(
        output_path=tmp_path,
        copy_metadata=True,
        metadata_parser_classes=(S2Metadata,),
    )
    path = (
        MPath.from_inp(tmp_path)
        / "sentinel-2-l2a"
        / "S2B_33TWM_20230810_0_L2A"
        / "GRANULE"
        / "L2A_T33TWM_A033567_20230810T095651"
        / "QI_DATA"
    )
    assert path.ls()
    for f in path.ls():
        assert f.suffix == ".jp2"
        with rasterio_open(f) as src:
            assert src.meta


def test_static_catalog_cloud_percent(s2_stac_collection):
    all_products = STACStaticCatalog(s2_stac_collection)
    filtered_products = STACStaticCatalog(
        s2_stac_collection, config=StacStaticConfig(max_cloud_cover=20)
    )
    assert len(all_products.items) > len(filtered_products.items)


def test_earthsearch_catalog_cloud_percent():
    all_products = EarthSearchV1S2L2A(
        collections=["sentinel-2-l2a"],
        time=TimeRange(start="2022-04-01", end="2022-04-03"),
        bounds=[16.3916015625, 48.69140625, 16.41357421875, 48.71337890625],
    )
    filtered_products = EarthSearchV1S2L2A(
        collections=["sentinel-2-l2a"],
        time=TimeRange(start="2022-04-01", end="2022-04-03"),
        bounds=[16.3916015625, 48.69140625, 16.41357421875, 48.71337890625],
        config=StacSearchConfig(max_cloud_cover=20),
    )
    assert len(all_products.items) > len(filtered_products.items)


def test_awssearch_catalog_cloud_percent():
    all_products = AWSSearchCatalogS2L2A(
        collections=["sentinel-s2-l2a"],
        time=TimeRange(start="2022-04-01", end="2022-04-03"),
        bounds=[16.3916015625, 48.69140625, 16.41357421875, 48.71337890625],
    )
    filtered_products = AWSSearchCatalogS2L2A(
        collections=["sentinel-s2-l2a"],
        time=TimeRange(start="2022-04-01", end="2022-04-03"),
        bounds=[16.3916015625, 48.69140625, 16.41357421875, 48.71337890625],
        config=UTMSearchConfig(max_cloud_cover=20),
    )
    assert len(all_products.items) > len(filtered_products.items)
