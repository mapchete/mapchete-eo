import os

import pystac
import pytest
from mapchete.testing import ProcessFixture

from mapchete_eo.discovery import STACSearchCatalog
from mapchete_eo.known_catalogs import E84Sentinel2COGs

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
TESTDATA_DIR = os.path.join(SCRIPT_DIR, "testdata")


@pytest.fixture
def s2_stac_collection():
    return os.path.join(TESTDATA_DIR, "s2_stac_collection", "catalog.json")


@pytest.fixture
def pf_sr_stac_collection():
    return os.path.join(
        TESTDATA_DIR, "pf_stac_collection", "stac", "SR", "catalog.json"
    )


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
            "collection",
            "S2A_MSIL2A_20181229T095411_N0211_R079_T33SVB_20181229T112231",
            "S2A_MSIL2A_20181229T095411_N0211_R079_T33SVB_20181229T112231.json",
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
