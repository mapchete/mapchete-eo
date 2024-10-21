import logging

from mapchete import Timer
from mapchete.io.raster import ReferencedRaster

from mapchete_eo.brdf import get_brdf_param
from mapchete_eo.brdf.config import BRDFModels
from mapchete_eo.exceptions import BRDFError
from mapchete_eo.platforms.sentinel2.config import L2ABandFParams
from mapchete_eo.platforms.sentinel2.metadata_parser import S2Metadata
from mapchete_eo.platforms.sentinel2.types import (
    L2ABand,
    Resolution,
)

logger = logging.getLogger(__name__)


def correction_grid(
    s2_metadata: S2Metadata,
    band: L2ABand,
    model: BRDFModels = BRDFModels.default,
    brdf_weight: float = 1.0,
    resolution: Resolution = Resolution["60m"],
    footprints_cached_read: bool = False,
) -> ReferencedRaster:
    with Timer() as t:
        brdf_params = get_brdf_param(
            f_band_params=L2ABandFParams[band.name].value,
            grid=s2_metadata.grid(resolution),
            product_crs=s2_metadata.crs,
            sun_azimuth_angle_array=s2_metadata.sun_angles.azimuth.raster.data,
            sun_zenith_angle_array=s2_metadata.sun_angles.zenith.raster.data,
            detector_footprints=s2_metadata.detector_footprints(
                band, cached_read=footprints_cached_read
            ),
            viewing_azimuth_per_detector=s2_metadata.viewing_incidence_angles(
                band
            ).azimuth.detectors,
            viewing_zenith_per_detector=s2_metadata.viewing_incidence_angles(
                band
            ).zenith.detectors,
            model=model,
            brdf_weight=brdf_weight,
        )
    if not brdf_params.any():  # pragma: no cover
        raise BRDFError(f"BRDF grid array for {s2_metadata.product_id} is empty!")
    logger.debug(
        f"BRDF for product {s2_metadata.product_id} band {band.value} calculated in {str(t)}"
    )
    return ReferencedRaster(
        data=brdf_params,
        transform=s2_metadata.transform(resolution),
        crs=s2_metadata.crs,
        bounds=s2_metadata.bounds,
        driver="COG",
    )
