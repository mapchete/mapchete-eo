import numpy as np
import numpy.ma as ma
import pytest
from fiona.transform import transform

from mapchete_eo.brdf import (
    apply_brdf_correction,
    get_brdf_param,
    get_constant_sun_angle,
)
from mapchete_eo.brdf.config import F_MODIS_PARAMS
from mapchete_eo.platforms.sentinel2 import S2Metadata
from mapchete_eo.platforms.sentinel2.brdf import L2ABandFParams
from mapchete_eo.platforms.sentinel2.types import (
    L2ABand,
    Resolution,
    SunAngle,
    ViewAngle,
)


@pytest.mark.remote
def test_run_sentinel2_brdf(s2_l2a_metadata_xml):
    band = L2ABand.B02
    metadata = S2Metadata.from_metadata_xml(s2_l2a_metadata_xml)
    _, (bottom, top) = transform(
        metadata.crs,
        "EPSG:4326",
        [metadata.bounds[0], metadata.bounds[2]],
        [metadata.bounds[1], metadata.bounds[3]],
    )
    height, width = metadata.shape(resolution=Resolution["60m"])
    band_array = ma.masked_equal(
        np.concatenate(
            (
                np.zeros((height, width // 2), dtype=np.uint16),
                np.full((height, width // 2), 500, dtype=np.uint16),
            ),
            axis=1,
        ),
        0,
    )
    corrected = apply_brdf_correction(
        band=band_array,
        f_band_params=L2ABandFParams[band.name].value,
        band_crs=metadata.crs,
        band_transform=metadata.transform(Resolution["60m"]),
        product_crs=metadata.crs,
        sun_azimuth_angle_array=metadata.sun_angles[SunAngle.azimuth],
        sun_zenith_angle_array=metadata.sun_angles[SunAngle.zenith],
        detector_footprints=metadata.detector_footprints(band),
        viewing_azimuth=metadata.viewing_incidence_angles(band)[ViewAngle.azimuth][
            "detector"
        ],
        viewing_zenith=metadata.viewing_incidence_angles(band)[ViewAngle.zenith][
            "detector"
        ],
        sun_zenith_angle=get_constant_sun_angle(min_lat=bottom, max_lat=top),
        model="HLS",
    )
    assert isinstance(corrected, ma.MaskedArray)
    assert not ma.allclose(band_array, corrected)
    assert np.allclose(band_array.mask, corrected.mask)


@pytest.mark.parametrize("band", [band for band in L2ABand if band != L2ABand.B10])
def test_get_all_12_bands_brdf_param(s2_l2a_metadata_xml, band):
    metadata = S2Metadata.from_metadata_xml(s2_l2a_metadata_xml)
    _, (bottom, top) = transform(
        metadata.crs,
        "EPSG:4326",
        [metadata.bounds[0], metadata.bounds[2]],
        [metadata.bounds[1], metadata.bounds[3]],
    )
    corrected = get_brdf_param(
        f_band_params=L2ABandFParams[band.name].value,
        grid=metadata.grid(Resolution["60m"]),
        product_crs=metadata.crs,
        sun_azimuth_angle_array=metadata.sun_angles[SunAngle.azimuth],
        sun_zenith_angle_array=metadata.sun_angles[SunAngle.zenith],
        detector_footprints=metadata.detector_footprints(band),
        viewing_azimuth=metadata.viewing_incidence_angles(band)[ViewAngle.azimuth][
            "detector"
        ],
        viewing_zenith=metadata.viewing_incidence_angles(band)[ViewAngle.zenith][
            "detector"
        ],
        sun_zenith_angle=get_constant_sun_angle(min_lat=bottom, max_lat=top),
        model="HLS",
    )
    assert isinstance(corrected, ma.MaskedArray)
    assert not corrected.mask.all()
    # This Value should be below 1 for all bands in this particular product
    assert np.nanmean(corrected) < 1.0
