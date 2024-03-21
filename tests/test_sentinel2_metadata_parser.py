import xml.etree.ElementTree as etree

import numpy as np
import numpy.ma as ma
import pytest
from affine import Affine
from mapchete.io.raster import ReferencedRaster
from mapchete.types import Bounds
from pystac import Item
from pytest_lazyfixture import lazy_fixture
from rasterio.crs import CRS
from shapely.geometry import shape

from mapchete_eo.exceptions import AssetEmpty, AssetMissing, CorruptedProductMetadata
from mapchete_eo.platforms.sentinel2.metadata_parser import S2Metadata
from mapchete_eo.platforms.sentinel2.path_mappers import (
    EarthSearchPathMapper,
    SinergisePathMapper,
    XMLMapper,
)
from mapchete_eo.platforms.sentinel2.processing_baseline import BaselineVersion
from mapchete_eo.platforms.sentinel2.types import (
    BandQI,
    CloudType,
    L2ABand,
    ProductQI,
    ProductQIMaskResolution,
    Resolution,
    SunAngle,
    ViewAngle,
)
from mapchete_eo.types import Grid


def test_xml_mapper(s2_l2a_metadata_xml):
    with s2_l2a_metadata_xml.open("rb") as metadata:
        xml_root = etree.parse(metadata).getroot()
        path_mapper = XMLMapper(
            metadata_xml=s2_l2a_metadata_xml,
            xml_root=xml_root,
        )
        band = L2ABand.B01

        for qi_mask in ProductQI:
            for resolution in ProductQIMaskResolution:
                path = path_mapper.product_qi_mask(
                    qi_mask=qi_mask, resolution=resolution
                )
                assert path.exists()
                if qi_mask != ProductQI.classification:
                    assert resolution.name in path.name

        for qi_mask in BandQI:
            assert path_mapper.band_qi_mask(qi_mask=qi_mask, band=band).exists()

        assert path_mapper.technical_quality_mask(band).exists()
        assert path_mapper.detector_footprints(band).exists()


@pytest.mark.remote
@pytest.mark.parametrize(
    "tileinfo, baseline_version",
    [
        (lazy_fixture("tileinfo_gml_schema"), "03.01"),
        (lazy_fixture("tileinfo_jp2_schema"), "04.00"),
    ],
)
def test_sinergise_mapper(tileinfo, baseline_version):
    path_mapper = SinergisePathMapper(tileinfo, baseline_version=baseline_version)

    for qi_mask in ProductQI:
        for resolution in ProductQIMaskResolution:
            path = path_mapper.product_qi_mask(qi_mask=qi_mask, resolution=resolution)
            assert path.exists()
            if qi_mask != ProductQI.classification:
                assert resolution.name in path.name

    band = L2ABand.B01
    for qi_mask in BandQI:
        assert path_mapper.band_qi_mask(qi_mask=qi_mask, band=band).exists()


@pytest.mark.remote
def test_earthsearch_mapper_jp2(s2_l2a_earthsearch_xml_remote):
    path_mapper = EarthSearchPathMapper(s2_l2a_earthsearch_xml_remote)

    for qi_mask in ProductQI:
        for resolution in ProductQIMaskResolution:
            path = path_mapper.product_qi_mask(qi_mask=qi_mask, resolution=resolution)
            assert path.exists()
            if qi_mask != ProductQI.classification:
                assert resolution.name in path.name

    band = L2ABand.B01
    for qi_mask in BandQI:
        assert path_mapper.band_qi_mask(qi_mask=qi_mask, band=band).exists()


@pytest.mark.parametrize(
    "metadata",
    [
        lazy_fixture("s2_l2a_metadata"),
    ],
)
def test_metadata_product_id(metadata):
    # product ID
    assert "L2A" in metadata.product_id


@pytest.mark.remote
@pytest.mark.parametrize(
    "metadata",
    [
        lazy_fixture("s2_l2a_metadata_remote"),
        lazy_fixture("s2_l2a_roda_metadata_remote"),
        lazy_fixture("s2_l2a_roda_metadata_jp2_masks_remote"),
        lazy_fixture("s2_l2a_earthsearch_remote"),
    ],
)
def test_remote_metadata_product_id(metadata):
    # product ID
    assert "L2A" in metadata.product_id


@pytest.mark.parametrize(
    "metadata",
    [lazy_fixture("s2_l2a_metadata")],
)
def test_metadata_crs(metadata):
    # crs
    assert isinstance(metadata.crs, CRS)


@pytest.mark.remote
@pytest.mark.parametrize(
    "metadata",
    [
        lazy_fixture("s2_l2a_metadata_remote"),
        lazy_fixture("s2_l2a_roda_metadata_remote"),
        lazy_fixture("s2_l2a_roda_metadata_jp2_masks_remote"),
        lazy_fixture("s2_l2a_earthsearch_remote"),
    ],
)
def test_remote_metadata_crs(metadata):
    # crs
    assert isinstance(metadata.crs, CRS)


def _test_metadata_bounds(metadata):
    # bounds
    assert isinstance(metadata.bounds, Bounds)
    assert len(metadata.bounds) == 4
    for i in metadata.bounds:
        assert isinstance(i, float)


@pytest.mark.parametrize(
    "metadata",
    [
        lazy_fixture("s2_l2a_metadata"),
    ],
)
def test_metadata_bounds(metadata):
    _test_metadata_bounds(metadata)


@pytest.mark.remote
@pytest.mark.parametrize(
    "metadata",
    [
        lazy_fixture("s2_l2a_metadata_remote"),
        lazy_fixture("s2_l2a_roda_metadata_remote"),
        lazy_fixture("s2_l2a_roda_metadata_jp2_masks_remote"),
        lazy_fixture("s2_l2a_earthsearch_remote"),
    ],
)
def test_remote_metadata_bounds(metadata):
    _test_metadata_bounds(metadata)


def _test_metadata_geoinfo(metadata, resolution):
    # grid
    assert isinstance(metadata.grid(resolution), Grid)

    # shape
    assert isinstance(metadata.shape(resolution), tuple)
    assert len(metadata.shape(resolution)) == 2
    for i in metadata.shape(resolution):
        assert isinstance(i, int)

    # transform
    assert isinstance(metadata.transform(resolution), Affine)
    assert metadata.transform(resolution)[0] == float(str(resolution.name).rstrip("m"))


@pytest.mark.parametrize(
    "metadata",
    [
        lazy_fixture("s2_l2a_metadata"),
    ],
)
@pytest.mark.parametrize(
    "resolution",
    [Resolution["10m"], Resolution["20m"], Resolution["60m"], Resolution["120m"]],
)
def test_metadata_geoinfo(metadata, resolution):
    _test_metadata_geoinfo(metadata, resolution)


@pytest.mark.remote
@pytest.mark.parametrize(
    "metadata",
    [
        lazy_fixture("s2_l2a_metadata_remote"),
        lazy_fixture("s2_l2a_roda_metadata_remote"),
        lazy_fixture("s2_l2a_roda_metadata_jp2_masks_remote"),
        lazy_fixture("s2_l2a_earthsearch_remote"),
    ],
)
@pytest.mark.parametrize(
    "resolution",
    [Resolution["10m"], Resolution["20m"], Resolution["60m"], Resolution["120m"]],
)
def test_remote_metadata_geoinfo(metadata, resolution):
    _test_metadata_geoinfo(metadata, resolution)


def _test_metadata_footprint(metadata):
    # footprint
    assert metadata.footprint.is_valid
    assert shape(metadata).is_valid
    assert metadata.footprint_latlon.is_valid


@pytest.mark.parametrize(
    "metadata",
    [
        lazy_fixture("s2_l2a_metadata"),
    ],
)
def test_metadata_footprint(metadata):
    _test_metadata_footprint(metadata)


@pytest.mark.remote
@pytest.mark.parametrize(
    "metadata",
    [
        lazy_fixture("s2_l2a_metadata_remote"),
        lazy_fixture("s2_l2a_roda_metadata_remote"),
        lazy_fixture("s2_l2a_roda_metadata_jp2_masks_remote"),
        lazy_fixture("s2_l2a_earthsearch_remote"),
    ],
)
def test_remote_metadata_footprint(metadata):
    _test_metadata_footprint(metadata)


def _test_metadata_l1c_cloud_mask(metadata):
    combined = metadata.l1c_cloud_mask()
    assert isinstance(combined, ReferencedRaster)
    assert combined.data.dtype == bool

    cirrus = metadata.l1c_cloud_mask(CloudType.cirrus)
    assert isinstance(cirrus, ReferencedRaster)
    assert cirrus.data.dtype == bool

    opaque = metadata.l1c_cloud_mask(CloudType.opaque)
    assert isinstance(opaque, ReferencedRaster)
    assert opaque.data.dtype == bool

    assert np.array_equal((cirrus.data + opaque.data).astype(bool), combined.data)


@pytest.mark.parametrize(
    "metadata",
    [
        lazy_fixture("s2_l2a_metadata"),
        lazy_fixture("s2_l2a_safe_metadata"),
    ],
)
def test_metadata_l1c_cloud_mask(metadata):
    _test_metadata_l1c_cloud_mask(metadata)


@pytest.mark.remote
@pytest.mark.parametrize(
    "metadata",
    [
        lazy_fixture("s2_l2a_metadata_remote"),
        lazy_fixture("s2_l2a_roda_metadata_remote"),
        lazy_fixture("s2_l2a_roda_metadata_jp2_masks_remote"),
        lazy_fixture("s2_l2a_earthsearch_remote"),
    ],
)
def test_remote_metadata_l1c_cloud_mask(metadata):
    _test_metadata_l1c_cloud_mask(metadata)


def _test_metadata_snow_ice_mask(metadata):
    snow_ice = metadata.snow_ice_mask()
    assert isinstance(snow_ice, ReferencedRaster)
    assert snow_ice.data.dtype == bool


@pytest.mark.parametrize(
    "metadata",
    [
        lazy_fixture("s2_l2a_metadata"),
        lazy_fixture("s2_l2a_safe_metadata"),
    ],
)
def test_metadata_snow_ice_mask(metadata):
    _test_metadata_snow_ice_mask(metadata)


@pytest.mark.remote
@pytest.mark.parametrize(
    "metadata",
    [
        lazy_fixture("s2_l2a_metadata_remote"),
        lazy_fixture("s2_l2a_roda_metadata_remote"),
        lazy_fixture("s2_l2a_roda_metadata_jp2_masks_remote"),
        lazy_fixture("s2_l2a_earthsearch_remote"),
    ],
)
def test_remote_metadata_snow_ice_mask(metadata):
    _test_metadata_snow_ice_mask(metadata)


def _test_metadata_band_masks(metadata):
    bands = [L2ABand.B01, L2ABand.B04]
    # band_masks
    for band in bands:
        # detector footprints
        mask = metadata.detector_footprints(band)
        assert isinstance(mask, ReferencedRaster)
        assert mask.data.any()
        assert mask.data.max() < 10

        # technical quality mask
        mask = metadata.technical_quality_mask(band)
        assert isinstance(mask, ReferencedRaster)


@pytest.mark.parametrize(
    "metadata",
    [
        lazy_fixture("s2_l2a_metadata"),
    ],
)
def test_metadata_band_masks(metadata):
    _test_metadata_band_masks(metadata)


@pytest.mark.remote
@pytest.mark.parametrize(
    "metadata",
    [
        lazy_fixture("s2_l2a_metadata_remote"),
        lazy_fixture("s2_l2a_roda_metadata_remote"),
    ],
)
def test_remote_metadata_band_masks(metadata):
    _test_metadata_band_masks(metadata)


def _test_metadata_sun_angles(metadata):
    # sun_angles
    for angle, properties in metadata.sun_angles.items():
        assert angle in SunAngle

        # array
        raster = properties["raster"]
        assert isinstance(raster, ReferencedRaster)
        assert isinstance(raster.data, ma.MaskedArray)
        assert raster.data.ndim == 2
        assert raster.data.dtype == np.float32
        assert not raster.data.mask.all()

        # transform
        assert isinstance(raster.transform, Affine)
        assert raster.transform[0] == 5000.0

        # mean
        assert isinstance(properties["mean"], float)


@pytest.mark.parametrize(
    "metadata",
    [
        lazy_fixture("s2_l2a_metadata"),
    ],
)
def test_metadata_sun_angles(metadata):
    _test_metadata_sun_angles(metadata)


@pytest.mark.remote
@pytest.mark.parametrize(
    "metadata",
    [
        lazy_fixture("s2_l2a_metadata_remote"),
        lazy_fixture("s2_l2a_roda_metadata_remote"),
        lazy_fixture("s2_l2a_roda_metadata_jp2_masks_remote"),
        lazy_fixture("s2_l2a_earthsearch_remote"),
    ],
)
def test_remote_metadata_sun_angles(metadata):
    _test_metadata_sun_angles(metadata)


def _test_metadata_viewing_incidence_angles(metadata):
    band = L2ABand.B04
    grids = metadata.viewing_incidence_angles(band)

    for angle, items in grids.items():
        assert angle in ViewAngle
        # mean
        assert isinstance(items["mean"], float)
        # mean viewing angles
        arr = metadata.mean_viewing_incidence_angles(bands=band, angle=angle)
        assert not arr.mask.all()

        # detector footprints
        footprints = len(items["detector"])
        assert footprints
        assert set(list(range(1, footprints + 1))) == set(
            [x for x in np.unique(metadata.detector_footprints(band).data) if x != 0]
        )
        for detector_id, properties in items["detector"].items():
            assert isinstance(detector_id, int)

            # array
            raster = properties["raster"]
            assert isinstance(raster, ReferencedRaster)
            assert isinstance(raster.data, ma.MaskedArray)
            assert raster.data.ndim == 2
            assert raster.data.dtype == np.float32
            assert not raster.data.mask.all()

            # transform
            assert isinstance(raster.transform, Affine)
            assert raster.transform[0] == 5000.0


@pytest.mark.parametrize(
    "metadata",
    [
        lazy_fixture("s2_l2a_metadata"),
    ],
)
def test_metadata_viewing_incidence_angles(metadata):
    _test_metadata_viewing_incidence_angles(metadata)


@pytest.mark.remote
@pytest.mark.parametrize(
    "metadata",
    [
        lazy_fixture("s2_l2a_metadata_remote"),
        lazy_fixture("s2_l2a_roda_metadata_remote"),
        lazy_fixture("s2_l2a_roda_metadata_jp2_masks_remote"),
        lazy_fixture("s2_l2a_earthsearch_remote"),
    ],
)
def test_remote_metadata_viewing_incidence_angles(metadata):
    _test_metadata_viewing_incidence_angles(metadata)


def test_unavailable_metadata_xml():
    with pytest.raises(FileNotFoundError):
        S2Metadata.from_metadata_xml("unavailable_metadata.xml")


@pytest.mark.remote
@pytest.mark.parametrize(
    "item_url",
    [
        "https://earth-search.aws.element84.com/v0/collections/sentinel-s2-l2a-cogs/items/S2A_33TWN_20220701_0_L2A",
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/33/T/WL/2022/6/S2A_33TWL_20220614_0_L2A/S2A_33TWL_20220614_0_L2A.json",
    ],
)
def test_from_stac_item(item_url):
    item = Item.from_file(item_url)
    s2_metadata = S2Metadata.from_stac_item(item)
    assert s2_metadata.processing_baseline.version == "04.00"
    if item.properties.get("sentinel:boa_offset_applied", False) or item.properties.get(
        "earthsearch:boa_offset_applied", False
    ):
        offset = -1000
    else:
        offset = 0
    assert s2_metadata.reflectance_offset == offset


@pytest.mark.remote
@pytest.mark.parametrize(
    "item",
    [
        # these tests burn requests, slow down test suite and are not essential
        # lazy_fixture("stac_item_pb_l1c_0204"),
        # lazy_fixture("stac_item_pb_l1c_0205"),
        # lazy_fixture("stac_item_pb_l1c_0206"),
        # lazy_fixture("stac_item_pb0207"),
        # lazy_fixture("stac_item_pb0208"),
        # lazy_fixture("stac_item_pb0209"),
        # lazy_fixture("stac_item_pb0210"),
        # lazy_fixture("stac_item_pb0211"),
        # lazy_fixture("stac_item_pb0212"),
        # lazy_fixture("stac_item_pb0213"),
        lazy_fixture("stac_item_jp2_schema"),
        lazy_fixture("stac_item_pb0214"),
        lazy_fixture("stac_item_pb0300"),
        lazy_fixture("stac_item_pb0301"),
        lazy_fixture("stac_item_pb0400"),
        lazy_fixture("stac_item_pb0400_offset"),
        lazy_fixture("stac_item_pb0509"),
        lazy_fixture("stac_item_sentinel2_jp2"),
    ],
)
def test_from_stac_item_backwards(item):
    s2_metadata = S2Metadata.from_stac_item(item)
    assert s2_metadata.datastrip_id
    if item.properties.get("sentinel:boa_offset_applied", False) or item.properties.get(
        "earthsearch:boa_offset_applied", False
    ):
        offset = -1000
    else:
        offset = 0

    # make sure baseline version is as expected
    assert s2_metadata.processing_baseline.version == item.properties.get(
        "s2:processing_baseline", item.properties.get("sentinel2:processing_baseline")
    )

    # make sure offset is correct
    assert s2_metadata.reflectance_offset == offset

    # see if paths exist on prior versions
    for qi_mask in ProductQI:
        for resolution in ProductQIMaskResolution:
            path = s2_metadata.path_mapper.product_qi_mask(
                qi_mask=qi_mask, resolution=resolution
            )
            assert path.exists()
            if qi_mask != ProductQI.classification:
                assert resolution.name in path.name

    band = L2ABand.B01
    for qi_mask in BandQI:
        assert s2_metadata.path_mapper.band_qi_mask(qi_mask=qi_mask, band=band).exists()


@pytest.mark.remote
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


@pytest.mark.remote
def test_product_empty_detector_footprints(product_empty_detector_footprints):
    s2_product = S2Metadata.from_metadata_xml(product_empty_detector_footprints)
    with pytest.raises(AssetEmpty):
        s2_product.detector_footprints(L2ABand.B02)


@pytest.mark.remote
def test_product_missing_detector_footprints(product_missing_detector_footprints):
    s2_product = S2Metadata.from_metadata_xml(product_missing_detector_footprints)
    with pytest.raises(AssetMissing):
        s2_product.detector_footprints(L2ABand.B02)


@pytest.mark.parametrize(
    "item",
    [
        lazy_fixture("full_stac_item_pb0509"),
        lazy_fixture("stac_item_sentinel2_jp2"),
    ],
)
def test_full_product_paths(item):
    metadata = S2Metadata.from_stac_item(item)
    for name, path in metadata.assets.items():
        assert path.exists()


@pytest.mark.remote
@pytest.mark.parametrize(
    "item",
    [
        lazy_fixture("stac_item_jp2_schema"),
        lazy_fixture("stac_item_pb0214"),
        lazy_fixture("stac_item_pb0300"),
        lazy_fixture("stac_item_pb0301"),
        lazy_fixture("stac_item_pb0400"),
        lazy_fixture("stac_item_pb0400_offset"),
        lazy_fixture("stac_item_pb0509"),
        lazy_fixture("stac_item_sentinel2_jp2"),
    ],
)
def test_full_remote_product_paths(item):
    metadata = S2Metadata.from_stac_item(item)
    for path in metadata.assets.values():
        assert path.exists()


@pytest.mark.remote
def test_broken_metadata_xml(s2_l2a_earthsearch_xml_remote_broken):
    with pytest.raises(CorruptedProductMetadata):
        S2Metadata.from_metadata_xml(s2_l2a_earthsearch_xml_remote_broken)
