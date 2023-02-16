from affine import Affine
from mapchete.io import path_exists, fs_from_path
import numpy as np
import numpy.ma as ma
from pystac import Item
import pytest
from shapely.geometry import shape
import xml.etree.ElementTree as etree

from mapchete_eo.platforms.sentinel2.metadata_parser import (
    S2Metadata,
    SinergisePathMapper,
    XMLMapper,
    BaselineVersion,
    MissingAsset,
)


def test_xml_mapper(s2_l2a_metadata_xml):
    with fs_from_path(s2_l2a_metadata_xml).open(s2_l2a_metadata_xml, "rb") as metadata:
        xml_root = etree.parse(metadata).getroot()
        path_mapper = XMLMapper(
            metadata_xml=s2_l2a_metadata_xml,
            xml_root=xml_root,
        )

        assert path_exists(path_mapper.cloud_mask())
        band = "B01"
        for qi_mask in [
            "defective",
            "saturated",
            "nodata",
            "detector_footprints",
            "technical_quality",
        ]:
            assert path_exists(path_mapper.band_qi_mask(qi_mask=qi_mask, band=band))


def test_sinergise_mapper_gml(tileinfo_gml_schema):
    path_mapper = SinergisePathMapper(tileinfo_gml_schema, baseline_version="03.01")
    assert path_exists(path_mapper.cloud_mask())
    band = "B01"
    for qi_mask in [
        "defective",
        "saturated",
        "nodata",
        "detector_footprints",
        "technical_quality",
    ]:
        assert path_exists(path_mapper.band_qi_mask(qi_mask=qi_mask, band=band))


def test_sinergise_mapper_jp2(tileinfo_jp2_schema):
    path_mapper = SinergisePathMapper(tileinfo_jp2_schema)
    assert path_exists(path_mapper.cloud_mask())
    band = "B01"
    for qi_mask in [
        "detector_footprints",
        "technical_quality",
    ]:
        assert path_exists(path_mapper.band_qi_mask(qi_mask=qi_mask, band=band))

    for qi_mask in [
        "defective",
        "saturated",
        "nodata",
    ]:
        with pytest.raises(DeprecationWarning):
            path_mapper.band_qi_mask(qi_mask=qi_mask, band=band)


@pytest.mark.parametrize(
    "metadata_xml",
    [
        pytest.lazy_fixture("s2_l2a_metadata_xml"),
        pytest.lazy_fixture("s2_l2a_metadata_xml_remote"),
        pytest.lazy_fixture("s2_l2a_roda_metadata_xml_remote"),
        pytest.lazy_fixture("s2_l2a_roda_metadata_jp2_masks_xml_remote"),
    ],
)
def test_metadata_product_id(metadata_xml):
    metadata = S2Metadata.from_metadata_xml(metadata_xml)

    # product ID
    assert "L2A" in metadata.product_id


@pytest.mark.parametrize(
    "metadata_xml",
    [
        pytest.lazy_fixture("s2_l2a_metadata_xml"),
        pytest.lazy_fixture("s2_l2a_metadata_xml_remote"),
        pytest.lazy_fixture("s2_l2a_roda_metadata_xml_remote"),
        pytest.lazy_fixture("s2_l2a_roda_metadata_jp2_masks_xml_remote"),
    ],
)
def test_metadata_crs(metadata_xml):
    metadata = S2Metadata.from_metadata_xml(metadata_xml)

    # crs
    assert metadata.crs.startswith("EPSG")


@pytest.mark.parametrize(
    "metadata_xml",
    [
        pytest.lazy_fixture("s2_l2a_metadata_xml"),
        pytest.lazy_fixture("s2_l2a_metadata_xml_remote"),
        pytest.lazy_fixture("s2_l2a_roda_metadata_xml_remote"),
        pytest.lazy_fixture("s2_l2a_roda_metadata_jp2_masks_xml_remote"),
    ],
)
def test_metadata_bounds(metadata_xml):
    metadata = S2Metadata.from_metadata_xml(metadata_xml)
    # bounds
    assert isinstance(metadata.bounds, tuple)
    assert len(metadata.bounds) == 4
    for i in metadata.bounds:
        assert isinstance(i, float)


@pytest.mark.parametrize(
    "metadata_xml",
    [
        pytest.lazy_fixture("s2_l2a_metadata_xml"),
        pytest.lazy_fixture("s2_l2a_metadata_xml_remote"),
        pytest.lazy_fixture("s2_l2a_roda_metadata_xml_remote"),
        pytest.lazy_fixture("s2_l2a_roda_metadata_jp2_masks_xml_remote"),
    ],
)
def test_metadata_geoinfo(metadata_xml):
    metadata = S2Metadata.from_metadata_xml(metadata_xml)
    # geoinfo
    for res in ["10m", "20m", "60m", "120m"]:

        # shape
        assert isinstance(metadata.shape(res), tuple)
        assert len(metadata.shape(res)) == 2
        for i in metadata.shape(res):
            assert isinstance(i, int)

        # x_size
        assert isinstance(metadata.pixel_x_size(res), float)
        assert metadata.pixel_x_size(res) >= 0.0

        # y_size
        assert isinstance(metadata.pixel_y_size(res), float)
        assert metadata.pixel_y_size(res) <= 0.0

        # transform
        assert isinstance(metadata.transform(res), Affine)
        assert metadata.transform(res)[0] == float(res.rstrip("m"))


@pytest.mark.parametrize(
    "metadata_xml",
    [
        pytest.lazy_fixture("s2_l2a_metadata_xml"),
        pytest.lazy_fixture("s2_l2a_safe_metadata_xml"),
        pytest.lazy_fixture("s2_l2a_metadata_xml_remote"),
        pytest.lazy_fixture("s2_l2a_roda_metadata_xml_remote"),
        pytest.lazy_fixture("s2_l2a_roda_metadata_jp2_masks_xml_remote"),
    ],
)
def test_metadata_cloud_mask(metadata_xml):
    metadata = S2Metadata.from_metadata_xml(metadata_xml)
    # cloud mask
    assert isinstance(metadata.cloud_mask(), list)


@pytest.mark.parametrize(
    "metadata_xml",
    [
        pytest.lazy_fixture("s2_l2a_metadata_xml"),
        pytest.lazy_fixture("s2_l2a_metadata_xml_remote"),
        pytest.lazy_fixture("s2_l2a_roda_metadata_xml_remote"),
    ],
)
def test_metadata_band_masks(metadata_xml):
    band_ids = [1, 4]
    metadata = S2Metadata.from_metadata_xml(metadata_xml)
    # band_masks
    for band_id in band_ids:

        # detector footprints
        assert metadata.detector_footprints(band_id)
        for feature in metadata.detector_footprints(band_id):
            detector_id = feature["properties"]["detector_id"]
            assert isinstance(detector_id, int)
            assert shape(feature["geometry"]).is_valid

        # defective mask
        assert isinstance(metadata.defective_mask(band_id), list)
        for feature in metadata.defective_mask(band_id):
            assert shape(feature["geometry"]).is_valid

        # saturated mask
        assert isinstance(metadata.saturated_mask(band_id), list)
        for feature in metadata.saturated_mask(band_id):
            assert shape(feature["geometry"]).is_valid

        # nodata mask
        assert isinstance(metadata.nodata_mask(band_id), list)
        for feature in metadata.nodata_mask(band_id):
            assert shape(feature["geometry"]).is_valid

        # technical quality mask
        assert isinstance(metadata.technical_quality_mask(band_id), list)
        for feature in metadata.technical_quality_mask(band_id):
            assert shape(feature["geometry"]).is_valid


def test_metadata_deprecated_band_masks(s2_l2a_roda_metadata_jp2_masks_xml_remote):
    band_ids = [1, 4]
    metadata = S2Metadata.from_metadata_xml(s2_l2a_roda_metadata_jp2_masks_xml_remote)
    # band_masks
    for band_id in band_ids:

        # detector footprints
        assert metadata.detector_footprints(band_id)
        for feature in metadata.detector_footprints(band_id):
            detector_id = feature["properties"]["detector_id"]
            assert isinstance(detector_id, int)
            assert shape(feature["geometry"]).is_valid

        # defective mask
        with pytest.raises(DeprecationWarning):
            metadata.defective_mask(band_id)

        # saturated mask
        with pytest.raises(DeprecationWarning):
            metadata.saturated_mask(band_id)

        # nodata mask
        with pytest.raises(DeprecationWarning):
            metadata.nodata_mask(band_id)

        # technical quality mask
        assert isinstance(metadata.technical_quality_mask(band_id), list)
        for feature in metadata.technical_quality_mask(band_id):
            assert shape(feature["geometry"]).is_valid


@pytest.mark.parametrize(
    "metadata_xml",
    [
        pytest.lazy_fixture("s2_l2a_metadata_xml"),
        pytest.lazy_fixture("s2_l2a_metadata_xml_remote"),
        pytest.lazy_fixture("s2_l2a_roda_metadata_xml_remote"),
        pytest.lazy_fixture("s2_l2a_roda_metadata_jp2_masks_xml_remote"),
    ],
)
def test_metadata_sun_angles(metadata_xml):
    metadata = S2Metadata.from_metadata_xml(metadata_xml)
    # sun_angles
    for angle, properties in metadata.sun_angles.items():
        assert angle in ["zenith", "azimuth"]

        # array
        assert isinstance(properties["array"], ma.MaskedArray)
        assert properties["array"].ndim == 2
        assert properties["array"].dtype == np.float32
        assert not properties["array"].mask.all()

        # transform
        assert isinstance(properties["transform"], Affine)
        assert properties["transform"][0] == 5000.0

        # mean
        assert isinstance(properties["mean"], float)


@pytest.mark.parametrize(
    "metadata_xml",
    [
        pytest.lazy_fixture("s2_l2a_metadata_xml"),
        pytest.lazy_fixture("s2_l2a_metadata_xml_remote"),
        pytest.lazy_fixture("s2_l2a_roda_metadata_xml_remote"),
        pytest.lazy_fixture("s2_l2a_roda_metadata_jp2_masks_xml_remote"),
    ],
)
def test_metadata_viewing_incidence_angles(metadata_xml):
    band_ids = [1, 4]
    metadata = S2Metadata.from_metadata_xml(metadata_xml)
    # viewing incidence angles
    for band_id in band_ids:
        grids = metadata.viewing_incidence_angles(band_id)

        for angle, items in grids.items():
            assert angle in ["zenith", "azimuth"]

            # mean
            assert isinstance(items["mean"], float)

            # mean viewing angles
            arr = metadata.mean_viewing_incidence_angles(band_ids=band_ids, angle=angle)
            assert not arr.mask.all()

            # detector footprints
            footprints = len(items["detector"])
            assert footprints
            assert set(list(range(1, footprints + 1))) == set(
                [
                    i["properties"]["detector_id"]
                    for i in metadata.detector_footprints(band_id)
                ]
            )
            for detector_id, properties in items["detector"].items():
                assert isinstance(detector_id, int)

                # array
                assert isinstance(properties["array"], ma.MaskedArray)
                assert properties["array"].ndim == 2
                assert properties["array"].dtype == np.float32
                assert not properties["array"].mask.all()

                # transform
                assert isinstance(properties["transform"], Affine)
                assert properties["transform"][0] == 5000.0


def test_unavailable_metadata_xml():
    with pytest.raises(FileNotFoundError):
        S2Metadata.from_metadata_xml(
            "s3://sentinel-s2-l2a/tiles/60/V/WQ/2021/8/19/1/metadata.xml"
        )


def test_from_stac_item():
    s2_metadata = S2Metadata.from_stac_item(
        Item.from_file(
            "https://earth-search.aws.element84.com/v0/collections/sentinel-s2-l2a-cogs/items/S2A_33TWN_20220701_0_L2A"
        )
    )
    assert s2_metadata.processing_baseline.version == "04.00"
    assert s2_metadata.reflectance_offset == 0


@pytest.mark.parametrize(
    "item, expected_baseline, offset",
    [
        (pytest.lazy_fixture("stac_item_pb_l1c_0204"), "02.04", 0),
        (pytest.lazy_fixture("stac_item_pb_l1c_0205"), "02.05", 0),
        (pytest.lazy_fixture("stac_item_pb_l1c_0206"), "02.06", 0),
        (pytest.lazy_fixture("stac_item_pb0207"), "02.07", 0),
        (pytest.lazy_fixture("stac_item_pb0208"), "02.08", 0),
        (pytest.lazy_fixture("stac_item_pb0209"), "02.09", 0),
        (pytest.lazy_fixture("stac_item_pb0210"), "02.10", 0),
        (pytest.lazy_fixture("stac_item_pb0211"), "02.11", 0),
        (pytest.lazy_fixture("stac_item_pb0212"), "02.12", 0),
        (pytest.lazy_fixture("stac_item_pb0213"), "02.13", 0),
        (pytest.lazy_fixture("stac_item_pb0214"), "02.14", 0),
        (pytest.lazy_fixture("stac_item_pb0300"), "03.00", 0),
        (pytest.lazy_fixture("stac_item_pb0301"), "03.01", 0),
        (pytest.lazy_fixture("stac_item_pb0400"), "04.00", 0),
        (pytest.lazy_fixture("stac_item_pb0400_offset"), "04.00", -1000),
        (pytest.lazy_fixture("stac_item_pb0509"), "05.09", 0),
    ],
)
def test_from_stac_item_backwards(item, expected_baseline, offset):
    s2_metadata = S2Metadata.from_stac_item(item)

    # on E84 processing_baseline is only reported since PB 04.00
    if s2_metadata.processing_baseline.version == "04.00":
        assert s2_metadata.processing_baseline.version == item.properties.get(
            "sentinel:processing_baseline"
        )

    # make sure baseline version is as expected
    assert s2_metadata.processing_baseline.version == expected_baseline

    # make sure offset is correct
    assert s2_metadata.reflectance_offset == offset

    # see if paths exist on prior versions
    assert path_exists(s2_metadata.path_mapper.cloud_mask())
    band = "B01"
    for qi_mask in [
        "detector_footprints",
        "technical_quality",
    ]:
        assert path_exists(
            s2_metadata.path_mapper.band_qi_mask(qi_mask=qi_mask, band=band)
        )


def test_from_stac_item_invalid(stac_item_invalid_pb0001):
    S2Metadata.from_stac_item(stac_item_invalid_pb0001)


def test_baseline_version():
    pb0200 = BaselineVersion.from_string("02.00")
    pb0300 = BaselineVersion.from_string("03.00")
    pb0400 = BaselineVersion.from_string("04.00")

    # less
    assert pb0200 < pb0300
    assert pb0200 <= pb0300
    assert pb0200 < "03.00"
    assert pb0200 <= "03.00"

    # greater
    assert pb0400 > pb0300
    assert pb0400 >= pb0300
    assert pb0400 > "03.00"
    assert pb0400 >= "03.00"

    # equal
    assert pb0400 == pb0400
    assert pb0400 == "04.00"


def test_future_baseline_version():
    BaselineVersion.from_string("10.00")


def test_product_no_detector_footprints(product_no_detector_footprints):
    s2_product = S2Metadata.from_metadata_xml(product_no_detector_footprints)
    with pytest.raises(MissingAsset):
        s2_product.detector_footprints(2)
