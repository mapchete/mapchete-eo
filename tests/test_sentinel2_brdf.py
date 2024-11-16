import numpy as np
import numpy.ma as ma
import pytest

from mapchete_eo.platforms.sentinel2 import S2Metadata
from mapchete_eo.platforms.sentinel2.brdf import correction_values
from mapchete_eo.platforms.sentinel2.brdf.config import BRDFModels
from mapchete_eo.platforms.sentinel2.types import (
    L2ABand,
    Resolution,
)


@pytest.mark.remote
@pytest.mark.parametrize("per_detector", [True, False])
def test_run_sentinel2_brdf(s2_l2a_metadata_xml, per_detector):
    band = L2ABand.B02
    metadata = S2Metadata.from_metadata_xml(s2_l2a_metadata_xml)
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
    brdf_params = correction_values(
        s2_metadata=metadata,
        band=band,
        model=BRDFModels.HLS,
        per_detector=per_detector,
        resolution=Resolution["60m"],
    ).array

    corrected_band = band_array * brdf_params

    assert isinstance(corrected_band, ma.MaskedArray)
    assert not ma.allclose(band_array, corrected_band)
    assert np.allclose(band_array.mask, corrected_band.mask)


@pytest.mark.parametrize("band", [band for band in L2ABand if band != L2ABand.B10])
def test_get_all_12_bands_brdf_param(s2_l2a_metadata_xml, band):
    metadata = S2Metadata.from_metadata_xml(s2_l2a_metadata_xml)
    corrected = correction_values(
        s2_metadata=metadata, band=band, resolution=Resolution["120m"]
    ).array
    assert isinstance(corrected, ma.MaskedArray)
    assert not corrected.mask.all()
    # This Value should be below 1 for all bands in this particular product
    assert np.nanmean(corrected) < 1.0


def test_brdf_correction_values(stac_item_brdf):
    metadata = S2Metadata.from_stac_item(stac_item_brdf)
    corrected = correction_values(
        s2_metadata=metadata,
        band=L2ABand.B04,
        resolution=Resolution["120m"],
        per_detector=False,
    ).array
    assert isinstance(corrected, ma.MaskedArray)
    assert not corrected.mask.all()
    # This Value should be above 1 in this particular product
    assert np.max(corrected) > 1.0
    assert np.mean(corrected) > 1.0
