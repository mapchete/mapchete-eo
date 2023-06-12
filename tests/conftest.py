import os

import pystac
from pystac_client import Client
import pytest
from mapchete.path import MPath
from mapchete.testing import ProcessFixture
from mapchete.tile import BufferedTilePyramid

from mapchete_eo.known_catalogs import EarthSearchV1S2L2A
from mapchete_eo.search import STACSearchCatalog, STACStaticCatalog
from mapchete_eo.platforms.sentinel2.metadata_parser import S2Metadata

SCRIPT_DIR = MPath(os.path.dirname(os.path.realpath(__file__)))
TESTDATA_DIR = SCRIPT_DIR / "testdata"


@pytest.fixture
def s2_stac_collection():
    # generated with:
    # $ mapchete eo static-catalog tests/testdata/s2_stac_collection --start-time 2022-04-01 --end-time 2022-04-05 --bounds 16 48 17 49 -d --assets-dst-resolution 480 --assets red,green,blue,nir,granule_metadata
    return TESTDATA_DIR / "s2_stac_collection" / "catalog.json"


@pytest.fixture
def s2_stac_items(s2_stac_collection):
    client = Client.from_file(str(s2_stac_collection))
    collection = next(client.get_collections())
    collection.make_all_asset_hrefs_absolute()
    return list(collection.get_items())


@pytest.fixture
def pf_sr_stac_collection():
    return TESTDATA_DIR / "pf_stac_collection" / "stac" / "SR" / "catalog.json"


@pytest.fixture
def pf_sr_stac_item(pf_sr_stac_collection):
    catalog = STACStaticCatalog(pf_sr_stac_collection)
    return next(iter(catalog.items.values()))


@pytest.fixture
def pf_qa_stac_collection():
    return TESTDATA_DIR / "pf_stac_collection" / "stac" / "QA" / "catalog.json"


@pytest.fixture
def s2_stac_item():
    item = pystac.pystac.Item.from_file(
        str(
            TESTDATA_DIR.joinpath(
                "s2_stac_collection",
                "sentinel-2-l2a",
                "S2A_33UWP_20220405_0_L2A",
                "S2A_33UWP_20220405_0_L2A.json",
            )
        )
    )
    item.make_asset_hrefs_absolute()
    return item


@pytest.fixture
def stac_mapchete(tmp_path):
    with ProcessFixture(
        TESTDATA_DIR / "stac.mapchete",
        output_tempdir=tmp_path,
    ) as example:
        yield example


@pytest.fixture
def sentinel2_mapchete(tmp_path):
    with ProcessFixture(
        TESTDATA_DIR / "sentinel2.mapchete",
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
    return EarthSearchV1S2L2A(
        start_time="2022-06-01",
        end_time="2022-06-06",
        bounds=[16, 46, 17, 47],
        collections=["sentinel-2-l2a"],
    )


@pytest.fixture(scope="session")
def e84_cog_catalog_short():
    return EarthSearchV1S2L2A(
        start_time="2022-06-01",
        end_time="2022-06-03",
        bounds=[16, 46.4, 16.1, 46.5],
        collections=["sentinel-2-l2a"],
    )


@pytest.fixture(scope="session")
def s2_l2a_metadata_xml():
    return TESTDATA_DIR / "l2a_metadata" / "metadata.xml"


@pytest.fixture(scope="session")
def s2_l2a_metadata(s2_l2a_metadata_xml):
    return S2Metadata.from_metadata_xml(s2_l2a_metadata_xml)


@pytest.fixture(scope="session")
def s2_l2a_safe_metadata():
    return S2Metadata.from_metadata_xml(
        str(
            TESTDATA_DIR.joinpath(
                "SAFE",
                "S2A_MSIL2A_20181229T095411_N0211_R079_T33SVB_20181229T112231",
                "S2A_MSIL2A_20181229T095411_N0211_R079_T33SVB_20181229T112231.SAFE",
                "MTD_MSIL2A.xml",
            )
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
    return MPath(
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/33/T/WL/2022/6/S2A_33TWL_20220601_0_L2A/granule_metadata.xml"
    )


@pytest.fixture(scope="session")
def s2_l2a_earthsearch_remote():
    """Metadata used by Earth-Search V1 endpoint"""
    return S2Metadata.from_stac_item(
        pystac.Item.from_file(
            "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/33/T/WL/2022/6/S2A_33TWL_20220601_0_L2A/S2A_33TWL_20220601_0_L2A.json"
        )
    )


@pytest.fixture()
def tileinfo_gml_schema():
    return "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/33/T/WL/2020/6/6/0/tileInfo.json"


@pytest.fixture()
def tileinfo_jp2_schema():
    return "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/33/T/WL/2022/6/6/0/tileInfo.json"


@pytest.fixture(scope="session")
def stac_item_pb0509():
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_32TMS_20221207_0_L2A"""
    return pystac.Item.from_file(
        str(TESTDATA_DIR / "stac_items" / "S2A_32TMS_20221207_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0400():
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20220130_0_L2A"""
    return pystac.Item.from_file(
        str(TESTDATA_DIR / "stac_items" / "S2B_33TWN_20220130_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0400_offset():
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20220226_0_L2A"""
    return pystac.Item.from_file(
        str(TESTDATA_DIR / "stac_items" / "S2B_33TWN_20220226_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0301():
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20220122_0_L2A"""
    return pystac.Item.from_file(
        str(TESTDATA_DIR / "stac_items" / "S2A_33TWN_20220122_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0300():
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20210629_0_L2A"""
    return pystac.Item.from_file(
        str(TESTDATA_DIR / "stac_items" / "S2A_33TWN_20210629_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0214():
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20210328_0_L2A"""
    return pystac.Item.from_file(
        str(TESTDATA_DIR / "stac_items" / "S2A_33TWN_20210328_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0213():
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20200202_0_L2A"""
    return pystac.Item.from_file(
        str(TESTDATA_DIR / "stac_items" / "S2A_33TWN_20200202_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0212():
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20190707_1_L2A"""
    return pystac.Item.from_file(
        str(TESTDATA_DIR / "stac_items" / "S2A_33TWN_20190707_1_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0211():
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20190503_0_L2A"""
    return pystac.Item.from_file(
        str(TESTDATA_DIR / "stac_items" / "S2B_33TWN_20190503_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0210():
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20181119_0_L2A"""
    return pystac.Item.from_file(
        str(TESTDATA_DIR / "stac_items" / "S2A_33TWN_20181119_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0209():
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20181104_0_L2A"""
    return pystac.Item.from_file(
        str(TESTDATA_DIR / "stac_items" / "S2B_33TWN_20181104_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0208():
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20181005_0_L2A"""
    return pystac.Item.from_file(
        str(TESTDATA_DIR / "stac_items" / "S2B_33TWN_20181005_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0207():
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20180521_1_L2A"""
    return pystac.Item.from_file(
        str(TESTDATA_DIR / "stac_items" / "S2B_33TWN_20180521_1_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb_l1c_0206():
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20180806_0_L2A"""
    return pystac.Item.from_file(
        str(TESTDATA_DIR / "stac_items" / "S2B_33TWN_20180806_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb_l1c_0205():
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20171005_0_L2A"""
    return pystac.Item.from_file(
        str(TESTDATA_DIR / "stac_items" / "S2A_33TWN_20171005_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb_l1c_0204():
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20161202_0_L2A"""
    return pystac.Item.from_file(
        str(TESTDATA_DIR / "stac_items" / "S2A_33TWN_20161202_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_invalid_pb0001():
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20180806_0_L2A"""
    return pystac.Item.from_file(
        str(TESTDATA_DIR / "stac_items" / "S2B_33TWN_20180806_0_L2A")
    )


@pytest.fixture()
def product_no_detector_footprints():
    return "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/34/R/FN/2022/4/15/0/metadata.xml"
