import os

import numpy as np
import numpy.ma as ma
import pystac
import pytest
from mapchete.path import MPath
from mapchete.testing import ProcessFixture
from mapchete.tile import BufferedTilePyramid
from pystac_client import Client
from rasterio import Affine
from shapely import wkt
from shapely.geometry import base

from mapchete_eo.known_catalogs import AWSSearchCatalogS2L2A, EarthSearchV1S2L2A
from mapchete_eo.platforms.sentinel2 import S2Metadata
from mapchete_eo.search import STACSearchCatalog, STACStaticCatalog
from mapchete_eo.types import TimeRange


@pytest.fixture
def tmp_mpath(tmp_path):
    return MPath.from_inp(tmp_path)


@pytest.fixture(scope="session")
def testdata_dir():
    return MPath(os.path.dirname(os.path.realpath(__file__))) / "testdata"


@pytest.fixture(scope="session")
def s2_testdata_dir(testdata_dir):
    return testdata_dir / "sentinel2"


@pytest.fixture(scope="session")
def eoxcloudless_testdata_dir(testdata_dir):
    return testdata_dir / "eoxcloudless"


@pytest.fixture(scope="session")
def s2_stac_collection(s2_testdata_dir):
    return s2_testdata_dir / "full_products" / "catalog.json"


@pytest.fixture(scope="session")
def s2_stac_items(s2_stac_collection):
    client = Client.from_file(str(s2_stac_collection))
    collection = next(client.get_collections())
    items = [item for item in collection.get_items()]
    for item in items:
        item.make_asset_hrefs_absolute()
    return items


@pytest.fixture
def pf_sr_stac_collection(testdata_dir):
    return testdata_dir / "pf_stac_collection" / "stac" / "SR" / "catalog.json"


@pytest.fixture
def pf_sr_stac_item(pf_sr_stac_collection):
    catalog = STACStaticCatalog(pf_sr_stac_collection)
    return next(iter(catalog.search()))


@pytest.fixture
def pf_qa_stac_collection(testdata_dir):
    return testdata_dir / "pf_stac_collection" / "stac" / "QA" / "catalog.json"


@pytest.fixture
def test_2d_array() -> ma.MaskedArray:
    data = np.random.randint(low=0, high=255, size=(256, 256), dtype=np.uint8)
    return ma.MaskedArray(
        data=data, mask=np.where(data <= 100, True, False), fill_value=0
    )


@pytest.fixture
def test_3d_array(test_2d_array) -> ma.MaskedArray:
    return ma.stack([test_2d_array for _ in range(3)])


@pytest.fixture
def test_4d_array(test_3d_array) -> ma.MaskedArray:
    return ma.stack([test_3d_array for _ in range(5)])


@pytest.fixture
def test_affine():
    return Affine(
        9783.939620502539,
        0.0,
        -20037508.3427892,
        0.0,
        -9783.939620502539,
        20037508.3427892,
        0.0,
        0.0,
        1.0,
    )


@pytest.fixture
def s2_stac_item(s2_stac_collection):
    item = pystac.pystac.Item.from_file(
        str(
            s2_stac_collection.parent
            / "sentinel-2-l2a"
            / "S2B_33TWM_20230810_0_L2A"
            / "S2B_33TWM_20230810_0_L2A.json"
        )
    )
    item.make_asset_hrefs_absolute()
    return item


@pytest.fixture
def s2_stac_item_jp2():
    item = pystac.pystac.Item.from_file(
        "s3://sentinel-s2-l2a-stac/2023/08/10/S2B_OPER_MSI_L2A_TL_2BPS_20230810T130104_A033567_T33TWM.json"
    )
    item.make_asset_hrefs_absolute()
    return item


@pytest.fixture
def s2_remote_stac_item():
    item = pystac.pystac.Item.from_file(
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/33/U/WP/2023/7/S2B_33UWP_20230704_0_L2A/S2B_33UWP_20230704_0_L2A.json"
    )
    return item


@pytest.fixture
def s2_stac_json_half_footprint(s2_stac_collection):
    return (
        s2_stac_collection.parent
        / "sentinel-2-l2a"
        / "S2B_33TWM_20230813_0_L2A"
        / "S2B_33TWM_20230813_0_L2A.json"
    )


@pytest.fixture
def s2_stac_item_half_footprint(s2_stac_json_half_footprint):
    item = pystac.pystac.Item.from_file(str(s2_stac_json_half_footprint))
    item.make_asset_hrefs_absolute()
    return item


@pytest.fixture
def stac_mapchete(tmp_path, testdata_dir):
    with ProcessFixture(
        testdata_dir / "stac.mapchete",
        output_tempdir=tmp_path,
    ) as example:
        yield example


@pytest.fixture
def eoxcloudless_8bit_dtype_scale_mapchete(tmp_path, testdata_dir):
    with ProcessFixture(
        testdata_dir / "eoxcloudless_8bit_dtype_scale.mapchete",
        output_tempdir=tmp_path,
    ) as example:
        yield example


@pytest.fixture
def eoxcloudless_sentinel2_color_correction_mapchete(tmp_path, testdata_dir):
    with ProcessFixture(
        testdata_dir / "eoxcloudless_sentinel2_color_correction.mapchete",
        output_tempdir=tmp_path,
    ) as example:
        yield example


@pytest.fixture
def eoxcloudless_rgb_map_mapchete(tmp_path, testdata_dir):
    with ProcessFixture(
        testdata_dir / "eoxcloudless_sentinel2_rgb_map.mapchete",
        output_tempdir=tmp_path,
    ) as example:
        yield example


@pytest.fixture
def eoxcloudless_mosaic_mapchete(tmp_path, testdata_dir):
    with ProcessFixture(
        testdata_dir / "eoxcloudless_mosaic.mapchete",
        output_tempdir=tmp_path,
    ) as example:
        yield example


@pytest.fixture
def sentinel2_antimeridian_east_mapchete(tmp_path, testdata_dir):
    with ProcessFixture(
        testdata_dir / "sentinel2_antimeridian_east.mapchete",
        output_tempdir=tmp_path,
    ) as example:
        yield example


@pytest.fixture
def sentinel2_antimeridian_west_mapchete(tmp_path, testdata_dir):
    with ProcessFixture(
        testdata_dir / "sentinel2_antimeridian_west.mapchete",
        output_tempdir=tmp_path,
    ) as example:
        yield example


@pytest.fixture
def eoxcloudless_mosaic_regions_merge_mapchete(tmp_path, testdata_dir):
    with ProcessFixture(
        testdata_dir / "eoxcloudless_mosaic_regions_merge.mapchete",
        output_tempdir=tmp_path,
    ) as example:
        yield example


@pytest.fixture
def sentinel2_mapchete(tmp_path, testdata_dir):
    with ProcessFixture(
        testdata_dir / "sentinel2.mapchete",
        output_tempdir=tmp_path,
    ) as example:
        yield example


@pytest.fixture
def sentinel2_csde_mapchete(tmp_path, testdata_dir):
    with ProcessFixture(
        testdata_dir / "sentinel2_csde.mapchete",
        output_tempdir=tmp_path,
    ) as example:
        yield example


@pytest.fixture
def sentinel2_cloud_cover_mapchete(tmp_path, testdata_dir):
    with ProcessFixture(
        testdata_dir / "sentinel2_cloud_cover.mapchete",
        output_tempdir=tmp_path,
    ) as example:
        yield example


@pytest.fixture
def sentinel2_mercator_mapchete(tmp_path, testdata_dir):
    with ProcessFixture(
        testdata_dir / "sentinel2_mercator.mapchete",
        output_tempdir=tmp_path,
    ) as example:
        yield example


@pytest.fixture
def sentinel2_jp2_static_catalog_mapchete(tmp_path, testdata_dir):
    with ProcessFixture(
        testdata_dir / "sentinel2_jp2_static_catalog.mapchete",
        output_tempdir=tmp_path,
    ) as example:
        yield example


@pytest.fixture
def sentinel2_area_mapchete(tmp_path, testdata_dir):
    with ProcessFixture(
        testdata_dir / "sentinel2_area.mapchete",
        output_tempdir=tmp_path,
    ) as example:
        yield example


@pytest.fixture
def sentinel2_time_ranges_mapchete(tmp_path, testdata_dir):
    with ProcessFixture(
        testdata_dir / "sentinel2_time_ranges.mapchete",
        output_tempdir=tmp_path,
    ) as example:
        yield example


@pytest.fixture
def sentinel2_stac_mapchete(tmp_path, testdata_dir):
    with ProcessFixture(
        testdata_dir / "sentinel2_stac.mapchete",
        output_tempdir=tmp_path,
    ) as example:
        yield example


@pytest.fixture
def sentinel2_stac_cloud_cover_mapchete(tmp_path, testdata_dir):
    with ProcessFixture(
        testdata_dir / "sentinel2_stac_cloud_cover.mapchete",
        output_tempdir=tmp_path,
    ) as example:
        yield example


@pytest.fixture
def sentinel2_stac_footprint_buffer_mapchete(tmp_path, testdata_dir):
    with ProcessFixture(
        testdata_dir / "sentinel2_stac_footprint_buffer.mapchete",
        output_tempdir=tmp_path,
    ) as example:
        yield example


@pytest.fixture
def sentinel2_stac_area_mapchete(tmp_path, testdata_dir):
    with ProcessFixture(
        testdata_dir / "sentinel2_stac_area.mapchete",
        output_tempdir=tmp_path,
    ) as example:
        yield example


@pytest.fixture
def merge_rasters_mapchete(tmp_path, testdata_dir):
    with ProcessFixture(
        testdata_dir / "merge_rasters.mapchete",
        output_tempdir=tmp_path,
    ) as example:
        yield example


@pytest.fixture
def cloudy_tile():
    return BufferedTilePyramid("geodetic").tile(13, 1986, 8557)


@pytest.fixture
def test_tile():
    """Tile on the overlap between MGRS granules 33TWL and 33TWM."""
    return BufferedTilePyramid("geodetic").tile_from_xy(15.77928, 46.01972, 13)


@pytest.fixture
def test_edge_tile():
    """Tile on the overlap between MGRS granules 33TWL and 33TWM but on the product edge."""
    return BufferedTilePyramid("geodetic").tile_from_xy(15.00122, 45.98486, 13)


@pytest.fixture(scope="session")
def stac_search_catalog():
    return STACSearchCatalog(
        collection="sentinel-2-l2a",
        time=TimeRange(
            start="2022-06-01",
            end="2022-06-06",
        ),
        bounds=[16, 46, 17, 47],
        endpoint="https://earth-search.aws.element84.com/v1/",
    )


@pytest.mark.remote
@pytest.fixture(scope="session")
def e84_cog_catalog():
    return EarthSearchV1S2L2A(
        collections=["sentinel-2-l2a"],
    )


@pytest.mark.remote
@pytest.fixture
def utm_search_catalog():
    return AWSSearchCatalogS2L2A(
        collections=["sentinel-s2-l2a"],
    )


@pytest.fixture(scope="session")
def e84_cog_catalog_short():
    return EarthSearchV1S2L2A(
        time=TimeRange(
            start="2022-06-01",
            end="2022-06-03",
        ),
        bounds=[16, 46.4, 16.1, 46.5],
        collections=["sentinel-2-l2a"],
    )


@pytest.fixture(scope="session")
def static_catalog_small(s2_stac_collection):
    return STACStaticCatalog(
        s2_stac_collection,
    )


@pytest.fixture(scope="session")
def s2_l2a_metadata_xml(s2_testdata_dir):
    return (
        s2_testdata_dir
        / "full_products"
        / "sentinel-2-l2a"
        / "S2B_33TWM_20230810_0_L2A"
        / "granule_metadata.xml"
    )


@pytest.fixture(scope="session")
def s2_l2a_metadata(s2_l2a_metadata_xml):
    return S2Metadata.from_metadata_xml(s2_l2a_metadata_xml)


@pytest.fixture(scope="session")
def s2_l2a_safe_metadata(s2_testdata_dir):
    return S2Metadata.from_metadata_xml(
        str(
            s2_testdata_dir.joinpath(
                "SAFE",
                "S2A_MSIL2A_20181229T095411_N0211_R079_T33SVB_20181229T112231",
                "S2A_MSIL2A_20181229T095411_N0211_R079_T33SVB_20181229T112231.SAFE",
                "MTD_MSIL2A.xml",
            )
        )
    )


@pytest.mark.remote
@pytest.fixture(scope="session")
def s2_l2a_metadata_remote():
    return S2Metadata.from_metadata_xml(
        "s3://sentinel-s2-l2a/tiles/51/K/XR/2020/7/31/0/metadata.xml"
    )


@pytest.mark.remote
@pytest.fixture(scope="session")
def s2_l2a_roda_metadata_remote():
    """Same content as s2_l2a_metadata_remote, but hosted on different server."""
    return S2Metadata.from_metadata_xml(
        "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/51/K/XR/2020/7/31/0/metadata.xml"
    )


@pytest.mark.remote
@pytest.fixture(scope="session")
def s2_l2a_roda_metadata_jp2_masks_remote():
    """From about 2022 on, ahte masks are now encoded as JP2 (rasters), not as GMLs (features)."""
    return S2Metadata.from_metadata_xml(
        "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/33/T/WL/2022/6/6/0/metadata.xml"
    )


@pytest.mark.remote
@pytest.fixture()
def s2_l2a_earthsearch_xml_remote():
    """Metadata used by Earth-Search V1 endpoint"""
    return MPath(
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/33/T/WL/2022/6/S2A_33TWL_20220601_0_L2A/granule_metadata.xml"
    )


@pytest.mark.remote
@pytest.fixture()
def s2_l2a_earthsearch_xml_remote_broken():
    """Metadata used by Earth-Search V1 endpoint"""
    return MPath(
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/21/N/TD/2023/6/S2A_21NTD_20230604_0_L2A/granule_metadata.xml"
    )


@pytest.mark.remote
@pytest.fixture(scope="session")
def s2_l2a_earthsearch_remote(s2_l2a_earthsearch_remote_item):
    """Metadata used by Earth-Search V1 endpoint"""
    return S2Metadata.from_stac_item(s2_l2a_earthsearch_remote_item)


@pytest.mark.remote
@pytest.fixture(scope="session")
def s2_l2a_earthsearch_remote_item():
    """Metadata used by Earth-Search V1 endpoint"""
    return pystac.Item.from_file(
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/33/T/WL/2022/6/S2A_33TWL_20220601_0_L2A/S2A_33TWL_20220601_0_L2A.json"
    )


@pytest.fixture()
def tileinfo_gml_schema():
    return "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/33/T/WL/2020/6/6/0/tileInfo.json"


@pytest.fixture()
def tileinfo_jp2_schema():
    return "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/33/T/WL/2022/6/6/0/tileInfo.json"


@pytest.fixture(scope="session")
def stac_item_brdf(s2_testdata_dir):
    return pystac.Item.from_file(
        str(
            s2_testdata_dir
            / "stac_items"
            / "S2A_12RWT_20240106_0_L2A"
            / "S2A_12RWT_20240106_0_L2A.json"
        )
    )


@pytest.fixture(scope="session")
def stac_item_pb0509(s2_testdata_dir):
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_32TMS_20221207_0_L2A"""
    return pystac.Item.from_file(
        str(s2_testdata_dir / "stac_items" / "S2A_32TMS_20221207_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0400(s2_testdata_dir):
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20220130_0_L2A"""
    return pystac.Item.from_file(
        str(s2_testdata_dir / "stac_items" / "S2B_33TWN_20220130_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0400_offset(s2_testdata_dir):
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20220226_0_L2A"""
    return pystac.Item.from_file(
        str(s2_testdata_dir / "stac_items" / "S2B_33TWN_20220226_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0301(s2_testdata_dir):
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20220122_0_L2A"""
    return pystac.Item.from_file(
        str(s2_testdata_dir / "stac_items" / "S2A_33TWN_20220122_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0300(s2_testdata_dir):
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20210629_0_L2A"""
    return pystac.Item.from_file(
        str(s2_testdata_dir / "stac_items" / "S2A_33TWN_20210629_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0214(s2_testdata_dir):
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20210328_0_L2A"""
    return pystac.Item.from_file(
        str(s2_testdata_dir / "stac_items" / "S2A_33TWN_20210328_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0213(s2_testdata_dir):
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20200202_0_L2A"""
    return pystac.Item.from_file(
        str(s2_testdata_dir / "stac_items" / "S2A_33TWN_20200202_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0212(s2_testdata_dir):
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20190707_1_L2A"""
    return pystac.Item.from_file(
        str(s2_testdata_dir / "stac_items" / "S2A_33TWN_20190707_1_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0211(s2_testdata_dir):
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20190503_0_L2A"""
    return pystac.Item.from_file(
        str(s2_testdata_dir / "stac_items" / "S2B_33TWN_20190503_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0210(s2_testdata_dir):
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20181119_0_L2A"""
    return pystac.Item.from_file(
        str(s2_testdata_dir / "stac_items" / "S2A_33TWN_20181119_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0209(s2_testdata_dir):
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20181104_0_L2A"""
    return pystac.Item.from_file(
        str(s2_testdata_dir / "stac_items" / "S2B_33TWN_20181104_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0208(s2_testdata_dir):
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20181005_0_L2A"""
    return pystac.Item.from_file(
        str(s2_testdata_dir / "stac_items" / "S2B_33TWN_20181005_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb0207(s2_testdata_dir):
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20180521_1_L2A"""
    return pystac.Item.from_file(
        str(s2_testdata_dir / "stac_items" / "S2B_33TWN_20180521_1_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb_l1c_0206(s2_testdata_dir):
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20180806_0_L2A"""
    return pystac.Item.from_file(
        str(s2_testdata_dir / "stac_items" / "S2B_33TWN_20180806_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb_l1c_0205(s2_testdata_dir):
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20171005_0_L2A"""
    return pystac.Item.from_file(
        str(s2_testdata_dir / "stac_items" / "S2A_33TWN_20171005_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_pb_l1c_0204(s2_testdata_dir):
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33TWN_20161202_0_L2A"""
    return pystac.Item.from_file(
        str(s2_testdata_dir / "stac_items" / "S2A_33TWN_20161202_0_L2A")
    )


@pytest.fixture(scope="session")
def stac_item_invalid_pb0001(s2_testdata_dir):
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_33TWN_20180806_0_L2A"""
    return pystac.Item.from_file(
        str(s2_testdata_dir / "stac_items" / "S2B_33TWN_20180806_0_L2A")
    )


@pytest.fixture(scope="session")
def full_stac_item_pb0509(s2_testdata_dir):
    return pystac.Item.from_file(
        s2_testdata_dir
        / "full_products"
        / "sentinel-2-l2a"
        / "S2B_33TWM_20230810_0_L2A"
        / "S2B_33TWM_20230810_0_L2A.json"
    )


@pytest.fixture(scope="session")
def antimeridian_item1(testdata_dir):
    return pystac.Item.from_file(
        testdata_dir
        / "antimeridian_items"
        / "S2A_OPER_MSI_L2A_TL_2APS_20230603T031757_A041497_T01WCQ.json"
    )


@pytest.fixture(scope="session")
def antimeridian_item2(testdata_dir):
    return pystac.Item.from_file(
        testdata_dir
        / "antimeridian_items"
        / "S2B_OPER_MSI_L2A_TL_2BPS_20230503T100334_A030615_T60VXH.json"
    )


@pytest.fixture(scope="session")
def antimeridian_item3(testdata_dir):
    return pystac.Item.from_file(
        testdata_dir
        / "antimeridian_items"
        / "S2B_OPER_MSI_L2A_TL_2BPS_20230512T234921_A032288_T01VCG.json"
    )


@pytest.fixture(scope="session")
def antimeridian_item4(testdata_dir):
    return pystac.Item.from_file(
        testdata_dir
        / "antimeridian_items"
        / "S2B_OPER_MSI_L2A_TL_2BPS_20230513T005426_A032288_T01VCG.json"
    )


@pytest.fixture(scope="session")
def antimeridian_item5(testdata_dir):
    return pystac.Item.from_file(
        testdata_dir
        / "antimeridian_items"
        / "S2A_OPER_MSI_L2A_TL_2APS_20230730T020155_A042312_T01VCC.json"
    )


@pytest.fixture(scope="session")
def antimeridian_broken_item(testdata_dir):
    # this footprint is unfuckingfixable
    return pystac.Item.from_file(
        testdata_dir
        / "antimeridian_items"
        / "S2A_OPER_MSI_L2A_TL_2APS_20230806T022123_A042412_T60VXH.json"
    )


@pytest.fixture()
def product_empty_detector_footprints():
    return "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/34/R/FN/2022/4/15/0/metadata.xml"


@pytest.fixture()
def product_missing_detector_footprints():
    return "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/37/W/EP/2023/10/17/0/metadata.xml"


@pytest.fixture(scope="session")
def stac_item_missing_detector_footprints():
    return pystac.Item.from_file(
        "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_37WEP_20231017_0_L2A"
    )


@pytest.fixture(scope="session")
def stac_item_path_sentinel2_jp2():
    return MPath(
        "s3://sentinel-s2-l2a-stac/2023/09/27/S2B_OPER_MSI_L2A_TL_2BPS_20230927T123351_A034253_T32MRS.json"
    )


@pytest.fixture(scope="session")
def stac_item_sentinel2_jp2(stac_item_path_sentinel2_jp2):
    return pystac.Item.from_file(stac_item_path_sentinel2_jp2)


@pytest.fixture(scope="session")
def stac_item_sentinel2_jp2_local(s2_testdata_dir):
    """https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_32TMS_20221207_0_L2A"""
    return pystac.Item.from_file(
        str(
            s2_testdata_dir
            / "stac_items"
            / "S2A_OPER_MSI_L2A_TL_2APS_20230602T025701_A041483_T01WCR.json"
        )
    )


@pytest.fixture(scope="session")
def broken_footprint() -> base.BaseGeometry:
    return wkt.loads(
        "MULTIPOLYGON (((-179.03242760827868 28.825599176471762, -179.0308811577117 28.826887224571962, -179.02586222138643 28.825701299969626, -179.03242760827868 28.825599176471762)), ((179.92625843344484 28.80535581623132, 179.91906671908546 29.04865837641597, -179.98863882201528 29.030540342977034, -179.98511826102327 29.03153223273561, -179.74178951639604 28.982689739628036, -179.7378129230277 28.979721579768817, -179.5115274606451 28.932071807545526, -179.50249930933524 28.933629861785928, -179.26687296455978 28.881090523674473, -179.26356470312984 28.87706829232248, -179.1624685280018 28.853736688656234, -179.03689747719628 28.82552946553057, 179.92625843344484 28.80535581623132)))"
    )


@pytest.fixture
def utm_search_index(testdata_dir) -> MPath:
    return testdata_dir / "s2-jp2-fgb-catalog/index.fgb"


@pytest.fixture(autouse=False)
def set_cdse_test_env(monkeypatch):
    access_key = os.getenv("CDSE_S3_ACCESS_KEY")
    secret_key = os.getenv("CDSE_S3_ACCESS_SECRET")

    if access_key and secret_key:
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", access_key)
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", secret_key)
        monkeypatch.setenv(
            "AWS_ENDPOINT_URL", "https://eodata.dataspace.copernicus.eu/"
        )
        monkeypatch.setenv("AWS_S3_ENDPOINT", "eodata.dataspace.copernicus.eu")
        monkeypatch.setenv("AWS_VIRTUAL_HOSTING", "FALSE")
        monkeypatch.setenv("AWS_DEFAULT_REGION_EOX", "default")
    else:
        pytest.fail("CDSE AWS credentials not found in environment")
