import os

import pystac
from pystac_client import Client
import pytest
from mapchete.testing import ProcessFixture
from mapchete.tile import BufferedTilePyramid

from mapchete_eo.known_catalogs import E84Sentinel2COGs
from mapchete_eo.search import STACSearchCatalog, STACStaticCatalog

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
TESTDATA_DIR = os.path.join(SCRIPT_DIR, "testdata")


@pytest.fixture
def s2_stac_collection():
    # generated with:
    # $ mapchete eo static-catalog tests/testdata/s2_stac_collection --start-time 2022-04-01 --end-time 2022-04-05 --bounds 16 48 17 49 -d --assets-dst-resolution 480 --assets B04,B03,B02,B08
    return os.path.join(TESTDATA_DIR, "s2_stac_collection", "catalog.json")


@pytest.fixture
def s2_stac_items():
    client = Client.from_file(
        os.path.join(TESTDATA_DIR, "s2_stac_collection", "catalog.json")
    )
    collection = next(client.get_collections())
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
    item = pystac.Item.from_file(
        os.path.join(
            TESTDATA_DIR,
            "s2_stac_collection",
            "sentinel-s2-l2a-cogs",
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
        collection="sentinel-s2-l2a-cogs",
        start_time="2022-06-01",
        end_time="2022-06-06",
        bounds=[16, 46, 17, 47],
        endpoint="https://earth-search.aws.element84.com/v0/",
    )


@pytest.fixture(scope="session")
def e84_cog_catalog():
    return E84Sentinel2COGs(
        start_time="2022-06-01",
        end_time="2022-06-06",
        bounds=[16, 46, 17, 47],
    )


@pytest.fixture(scope="session")
def e84_cog_catalog_short():
    return E84Sentinel2COGs(
        start_time="2022-06-01",
        end_time="2022-06-03",
        bounds=[16, 46.4, 16.1, 46.5],
    )
