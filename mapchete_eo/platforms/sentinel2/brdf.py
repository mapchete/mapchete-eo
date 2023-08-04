from fiona.transform import transform
import logging
from pydantic import BaseModel
from retry import retry
from typing import List
from mapchete import Timer
from mapchete.path import MPath

from mapchete_eo.brdf import get_brdf_param, get_sun_angle_array
from mapchete_eo.brdf.config import BRDFModels
from mapchete_eo.io import cache_to_file
from mapchete_eo.exceptions import (
    BRDFError,
    CorruptedGTiffError,
)
from mapchete_eo.platforms.sentinel2.types import Resolution
from mapchete_eo.settings import MP_EO_IO_RETRY_SETTINGS

logger = logging.getLogger(__name__)


class BRDFConfig(BaseModel):
    model: BRDFModels = BRDFModels.HLS
    bands: List[str] = ["blue", "green", "red", "nir"]
    resolution: Resolution = Resolution["60m"]


def cache_brdf_correction_grids(
    product_id=None,
    s2_metadata=None,
    resolution=None,
    model=None,
    out_paths=None,
    uncached=None,
    check_cached_files_exist=False,
    cached_files_validation=False,
):
    """Cache BRDF correction grids"""
    for band_idx, out_path in out_paths.items():
        MPath(out_path).makedirs()

    _, (bottom, top) = transform(
        s2_metadata.crs,
        "EPSG:4326",
        [s2_metadata.bounds[0], s2_metadata.bounds[2]],
        [s2_metadata.bounds[1], s2_metadata.bounds[3]],
    )
    sun_zenith_angle = get_sun_angle_array(
        min_lat=bottom,
        max_lat=top,
        shape=s2_metadata.sun_angles["zenith"]["array"].shape,
    )
    for band_idx, out_path in uncached.items():
        # add to preprocessing task
        out_path = out_paths[band_idx]
        logger.debug("add BRDF grid generation to preprocessing tasks")
        cache_brdf_correction_grid(
            product_id=product_id,
            s2_metadata=s2_metadata,
            band_idx=band_idx,
            model=model,
            resolution=resolution,
            sun_zenith_angle=sun_zenith_angle,
            out_path=out_path,
            check_cached_files_exist=check_cached_files_exist,
            cached_files_validation=cached_files_validation,
        )


@retry(logger=logger, exceptions=CorruptedGTiffError, **MP_EO_IO_RETRY_SETTINGS)
def cache_brdf_correction_grid(
    product_id=None,
    s2_metadata=None,
    band_idx=None,
    model=None,
    resolution=None,
    sun_zenith_angle=None,
    out_path=None,
    check_cached_files_exist=False,
    cached_files_validation=False,
):
    logger.debug(f"run BRDF for product {product_id} band {band_idx}")

    with Timer() as t:
        brdf_params = get_brdf_param(
            band_idx=band_idx,
            out_shape=s2_metadata.shape(resolution),
            out_transform=s2_metadata.transform(resolution),
            product_crs=s2_metadata.crs,
            sun_angles=s2_metadata.sun_angles,
            detector_footprints=s2_metadata.detector_footprints(band_idx),
            viewing_incidence_angles=s2_metadata.viewing_incidence_angles(band_idx),
            sun_zenith_angle=sun_zenith_angle,
            model=model,
        )
    if not brdf_params.any():  # pragma: no cover
        raise BRDFError(f"BRDF grid array for {product_id} is empty!")

    out_transform = s2_metadata.transform(resolution)

    logger.debug(
        f"BRDF for product {product_id} band {band_idx} calculated in {str(t)}"
    )

    if check_cached_files_exist and MPath(out_path).exists():  # pragma: no cover
        logger.debug("%s already exists, skipping", out_path)
    else:
        cache_to_file(
            in_array=brdf_params,
            in_affine=out_transform,
            in_array_dtype="float32",
            nodata=0,
            crs=s2_metadata.crs,
            out_file_path=None,
            out_file_suffix=".tif",
        )
    if cached_files_validation:
        raise NotImplementedError()
    return out_path
