import os

import pystac
from pystac_client import Client
import pytest
from mapchete.testing import ProcessFixture
from mapchete.tile import BufferedTilePyramid

from mapchete_eo.known_catalogs import E84Sentinel2COGsV1
from mapchete_eo.search import STACSearchCatalog, STACStaticCatalog
from mapchete_eo.platforms.sentinel2.metadata_parser import S2Metadata

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
TESTDATA_DIR = os.path.join(SCRIPT_DIR, "testdata")


@pytest.fixture
def s2_stac_collection():
    # generated with:
    # $ mapchete eo static-catalog tests/testdata/s2_stac_collection --start-time 2022-04-01 --end-time 2022-04-05 --bounds 16 48 17 49 -d --assets-dst-resolution 480 --assets red,green,blue,nir,granule_metadata
    return os.path.join(TESTDATA_DIR, "s2_stac_collection", "catalog.json")


@pytest.fixture
def s2_stac_items():
    client = Client.from_file(
        os.path.join(TESTDATA_DIR, "s2_stac_collection", "catalog.json")
    )
    collection = next(client.get_collections())
    collection.make_all_asset_hrefs_absolute()
    return list(collection.get_items())


@pytest.fixture
def pf_sr_stac_collection():
    return os.path.join(
        TESTDATA_DIR, "pf_stac_collection", "stac", "SR", "catalog.json"
    )


@pytest.fixture
def pf_sr_stac_item():
    path = os.path.join(
        TESTDATA_DIR, "pf_stac_collection", "stac", "SR", "catalog.json"
    )
    catalog = STACStaticCatalog(path)
    return next(iter(catalog.items.values()))


@pytest.fixture
def pf_qa_stac_collection():
    return os.path.join(
        TESTDATA_DIR, "pf_stac_collection", "stac", "QA", "catalog.json"
    )


@pytest.fixture
def s2_stac_item():
    item = pystac.pystac.Item.from_file(
        os.path.join(
            TESTDATA_DIR,
            "s2_stac_collection",
            "sentinel-2-l2a",
            "S2A_33UWP_20220405_0_L2A",
            "S2A_33UWP_20220405_0_L2A.json",
        )
    )
    item.make_asset_hrefs_absolute()
    return item


@pytest.fixture
def stac_mapchete(tmp_path):
    with ProcessFixture(
        os.path.join(TESTDATA_DIR, "stac.mapchete"),
        output_tempdir=tmp_path,
    ) as example:
        yield example


@pytest.fixture
def sentinel2_mapchete(tmp_path):
    with ProcessFixture(
        os.path.join(TESTDATA_DIR, "sentinel2.mapchete"),
        output_tempdir=tmp_path,
    ) as example:
        yield example


@pytest.fixture
def test_tile():
    return BufferedTilePyramid("geodetic").tile(13, 1879, 8938)


@pytest.fixture(scope="session")
def stac_search_catalog():
    return STACSearchCatalog(
        collection="sentinel-2-l2a",
        start_time="2022-06-01",
        end_time="2022-06-06",
        bounds=[16, 46, 17, 47],
        endpoint="https://earth-search.aws.element84.com/v1/",
    )


@pytest.fixture(scope="session")
def e84_cog_catalog():
    return E84Sentinel2COGsV1(
        start_time="2022-06-01",
        end_time="2022-06-06",
        bounds=[16, 46, 17, 47],
    )


@pytest.fixture(scope="session")
def e84_cog_catalog_short():
    return E84Sentinel2COGsV1(
        start_time="2022-06-01",
        end_time="2022-06-03",
        bounds=[16, 46.4, 16.1, 46.5],
    )


@pytest.fixture()
def s2_l2a_metadata_xml():
    return os.path.join(*[TESTDATA_DIR, "l2a_metadata", "metadata.xml"])


@pytest.fixture(scope="session")
def s2_l2a_metadata():
    return S2Metadata.from_metadata_xml(
        os.path.join(*[TESTDATA_DIR, "l2a_metadata", "metadata.xml"])
    )


@pytest.fixture(scope="session")
def s2_l2a_safe_metadata():
    return S2Metadata.from_metadata_xml(
        os.path.join(
            *[
                TESTDATA_DIR,
                "SAFE",
                "S2A_MSIL2A_20181229T095411_N0211_R079_T33SVB_20181229T112231",
                "S2A_MSIL2A_20181229T095411_N0211_R079_T33SVB_20181229T112231.SAFE",
                "MTD_MSIL2A.xml",
            ]
        )
    )


@pytest.fixture(scope="session")
def s2_l2a_metadata_remote():
    return S2Metadata.from_metadata_xml(
        "s3://sentinel-s2-l2a/tiles/51/K/XR/2020/7/31/0/metadata.xml"
    )


@pytest.fixture(scope="session")
def s2_l2a_roda_metadata_remote():
    """Same content as s2_l2a_metadata_remote, but hosted on different server."""
    return S2Metadata.from_metadata_xml(
        "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/51/K/XR/2020/7/31/0/metadata.xml"
    )


@pytest.fixture(scope="session")
def s2_l2a_roda_metadata_jp2_masks_remote():
    """From about 2022 on, ahte masks are now encoded as JP2 (rasters), not as GMLs (features)."""
    return S2Metadata.from_metadata_xml(
        "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/33/T/WL/2022/6/6/0/metadata.xml"
    )


@pytest.fixture()
def s2_l2a_earthsearch_xml_remote():
    """Metadata used by Earth-Search V1 endpoint"""
    return "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/33/T/WL/2022/6/S2A_33TWL_20220601_0_L2A/granule_metadata.xml"


@pytest.fixture(scope="session")
def s2_l2a_earthsearch_remote():
    """Metadata used by Earth-Search V1 endpoint"""
    return S2Metadata.from_metadata_xml(
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/33/T/WL/2022/6/S2A_33TWL_20220601_0_L2A/granule_metadata.xml"
    )


@pytest.fixture()
def tileinfo_gml_schema():
    return "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/33/T/WL/2020/6/6/0/tileInfo.json"


@pytest.fixture()
def tileinfo_jp2_schema():
    return "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/33/T/WL/2022/6/6/0/tileInfo.json"


@pytest.fixture(scope="session")
def stac_item_pb0509():
    return pystac.Item.from_file(
        "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_32TMS_20221207_0_L2A"
    )


@pytest.fixture(scope="session")
def stac_item_pb0400():
    return pystac.Item.from_file(
        "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20220130_0_L2A"
    )


@pytest.fixture(scope="session")
def stac_item_pb0400_offset():
    return pystac.Item.from_file(
        "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20220226_0_L2A"
    )


@pytest.fixture(scope="session")
def stac_item_pb0301():
    return pystac.Item.from_file(
        "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20220122_0_L2A"
    )


@pytest.fixture(scope="session")
def stac_item_pb0300():
    return pystac.Item.from_file(
        "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20210629_0_L2A"
    )


@pytest.fixture(scope="session")
def stac_item_pb0214():
    return pystac.Item.from_file(
        "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20210328_0_L2A"
    )


@pytest.fixture(scope="session")
def stac_item_pb0213():
    return pystac.Item.from_file(
        "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20200202_0_L2A"
    )


@pytest.fixture(scope="session")
def stac_item_pb0212():
    return pystac.Item.from_file(
        "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20190707_1_L2A"
    )


@pytest.fixture(scope="session")
def stac_item_pb0211():
    return pystac.Item.from_file(
        "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20190503_0_L2A"
    )


@pytest.fixture(scope="session")
def stac_item_pb0210():
    return pystac.Item.from_file(
        "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20181119_0_L2A"
    )


@pytest.fixture(scope="session")
def stac_item_pb0209():
    return pystac.Item.from_file(
        "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20181104_0_L2A"
    )


@pytest.fixture(scope="session")
def stac_item_pb0208():
    return pystac.Item.from_file(
        "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20181005_0_L2A"
    )


@pytest.fixture(scope="session")
def stac_item_pb0207():
    return pystac.Item.from_file(
        "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20180521_1_L2A"
    )


@pytest.fixture(scope="session")
def stac_item_pb_l1c_0206():
    return pystac.Item.from_file(
        "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20180806_0_L2A"
    )


@pytest.fixture(scope="session")
def stac_item_pb_l1c_0205():
    return pystac.Item.from_file(
        "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20171005_0_L2A"
    )


@pytest.fixture(scope="session")
def stac_item_pb_l1c_0204():
    return pystac.Item.from_file(
        "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20161202_0_L2A"
    )


@pytest.fixture(scope="session")
def stac_item_invalid_pb0001():
    return pystac.Item.from_file(
        "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20180806_0_L2A"
    )


@pytest.fixture()
def product_no_detector_footprints():
    return "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/34/R/FN/2022/4/15/0/metadata.xml"
