import logging
from typing import Iterator, List, Optional

import numpy as np
from fiona.transform import transform
from mapchete import Timer
from mapchete.io.raster import ReferencedRaster

from mapchete_eo.brdf import get_brdf_param, get_sun_angle_array
from mapchete_eo.brdf.config import BRDFModels
from mapchete_eo.exceptions import BRDFError
from mapchete_eo.platforms.sentinel2.config import L2ABandFParams
from mapchete_eo.platforms.sentinel2.metadata_parser import S2Metadata
from mapchete_eo.platforms.sentinel2.types import (
    L2ABand,
    Resolution,
    SunAngle,
    ViewAngle,
)

logger = logging.getLogger(__name__)


def get_sun_zenith_angle(s2_metadata: S2Metadata):
    _, (bottom, top) = transform(
        s2_metadata.crs,
        "EPSG:4326",
        [s2_metadata.bounds[0], s2_metadata.bounds[2]],
        [s2_metadata.bounds[1], s2_metadata.bounds[3]],
    )
    return get_sun_angle_array(
        min_lat=bottom,
        max_lat=top,
        shape=s2_metadata.sun_angles[SunAngle.zenith]["raster"].data.shape,
    )


def correction_grid(
    s2_metadata: S2Metadata,
    band: L2ABand,
    sun_zenith_angle: Optional[np.ndarray] = None,
    model: BRDFModels = BRDFModels.default,
    resolution: Resolution = Resolution["60m"],
    footprints_cached_read: bool = False,
) -> ReferencedRaster:
    with Timer() as t:
        brdf_params = get_brdf_param(
            f_band_params=L2ABandFParams[band.name].value,
            grid=s2_metadata.grid(resolution),
            product_crs=s2_metadata.crs,
            sun_azimuth_angle_array=s2_metadata.sun_angles[SunAngle.azimuth],
            sun_zenith_angle_array=s2_metadata.sun_angles[SunAngle.zenith],
            detector_footprints=s2_metadata.detector_footprints(
                band, cached_read=footprints_cached_read
            ),
            viewing_azimuth=s2_metadata.viewing_incidence_angles(band)[
                ViewAngle.azimuth
            ]["detector"],
            viewing_zenith=s2_metadata.viewing_incidence_angles(band)[ViewAngle.zenith][
                "detector"
            ],
            sun_zenith_angle=get_sun_zenith_angle(s2_metadata)
            if sun_zenith_angle is None
            else sun_zenith_angle,
            model=model,
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


def correction_grids(
    s2_metadata: S2Metadata,
    bands: List[L2ABand],
    model: BRDFModels = BRDFModels.default,
    resolution: Resolution = Resolution["60m"],  # TODO use 120m?
) -> Iterator[ReferencedRaster]:
    for band in bands:
        logger.debug(
            "run BRDF for product %s band %s", s2_metadata.product_id, band.value
        )
        yield correction_grid(
            s2_metadata,
            band,
            get_sun_zenith_angle(s2_metadata),
            model=model,
            resolution=resolution,
        )
