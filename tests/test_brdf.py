from fiona.transform import transform
import numpy as np
import numpy.ma as ma
import pytest

from mapchete_eo.platforms.sentinel2 import S2Metadata
from mapchete_eo.platforms.sentinel2.types import Resolution
from mapchete_eo.brdf import get_brdf_param, run_brdf, get_constant_sun_angle


@pytest.mark.remote
def test_run_sentinel2_brdf(s2_l2a_metadata_xml):
    band_idx = 2
    metadata = S2Metadata.from_metadata_xml(s2_l2a_metadata_xml)
    _, (bottom, top) = transform(
        metadata.crs,
        "EPSG:4326",
        [metadata.bounds[0], metadata.bounds[2]],
        [metadata.bounds[1], metadata.bounds[3]],
    )
    height, width = metadata.shape(resolution=Resolution["60m"])
    band_data = np.concatenate(
        (
            np.zeros((height, width // 2), dtype=np.uint16),
            np.full((height, width // 2), 500, dtype=np.uint16),
        ),
        axis=1,
    )
    band = ma.masked_equal(band_data, 0)
    corrected = run_brdf(
        band=band,
        band_idx=band_idx,
        band_crs=metadata.crs,
        band_transform=metadata.transform(Resolution["60m"]),
        product_crs=metadata.crs,
        sun_angles=metadata.sun_angles,
        detector_footprints=metadata._get_band_mask(band_idx, "detector_footprints"),
        viewing_incidence_angles=metadata.viewing_incidence_angles(band_idx),
        sun_zenith_angle=get_constant_sun_angle(min_lat=bottom, max_lat=top),
        model="HLS",
    )
    assert isinstance(corrected, ma.MaskedArray)
    assert not ma.allclose(band, corrected)
    assert np.allclose(band.mask, corrected.mask)


def test_get_all_12_bands_brdf_param(s2_l2a_metadata_xml):
    band_idx_list = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    for band_idx in band_idx_list:
        metadata = S2Metadata.from_metadata_xml(s2_l2a_metadata_xml)
        _, (bottom, top) = transform(
            metadata.crs,
            "EPSG:4326",
            [metadata.bounds[0], metadata.bounds[2]],
            [metadata.bounds[1], metadata.bounds[3]],
        )
        corrected = get_brdf_param(
            band_idx=band_idx,
            out_shape=metadata.shape(Resolution["60m"]),
            out_transform=metadata.transform(Resolution["60m"]),
            product_crs=metadata.crs,
            sun_angles=metadata.sun_angles,
            detector_footprints=metadata._get_band_mask(
                band_idx, "detector_footprints"
            ),
            viewing_incidence_angles=metadata.viewing_incidence_angles(band_idx),
            sun_zenith_angle=get_constant_sun_angle(min_lat=bottom, max_lat=top),
            model="HLS",
        )

        if np.nanmean(corrected) < 1.0:
            raise ValueError(
                "This Value should be above 1 for this test data all bands!"
            )

        assert isinstance(corrected, ma.MaskedArray)
        assert not corrected.mask.all()
