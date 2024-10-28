import logging
from typing import Dict, List

from mapchete import Timer
from mapchete.io.raster import ReferencedRaster, resample_from_array
from mapchete.protocols import GridProtocol
from mapchete.types import NodataVal
import numpy as np
import numpy.ma as ma
from numpy.typing import DTypeLike
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.fill import fillnodata

from mapchete_eo.exceptions import BRDFError
from mapchete_eo.platforms.sentinel2.brdf.config import L2ABandFParams, ModelParameters
from mapchete_eo.platforms.sentinel2.brdf.models import BRDFModels, DirectionalModels
from mapchete_eo.platforms.sentinel2.metadata_parser import S2Metadata
from mapchete_eo.platforms.sentinel2.types import (
    L2ABand,
    Resolution,
)

logger = logging.getLogger(__name__)


def _correction_combine_detectors(
    product_crs: CRS,
    grid: GridProtocol,
    sun_azimuth_angle_array: np.ndarray,
    sun_zenith_angle_array: np.ndarray,
    f_band_params: ModelParameters,
    viewing_azimuth_angle_array: ReferencedRaster,
    viewing_zenith_angle_array: ReferencedRaster,
    model: BRDFModels = BRDFModels.default,
    brdf_weight: float = 1.0,
    dtype: DTypeLike = np.float32,
) -> ma.MaskedArray:
    """
    Run correction using combined angle masks of all
    """
    model_params = resample_from_array(
        DirectionalModels(
            angles=(
                sun_zenith_angle_array,
                sun_azimuth_angle_array,
                viewing_zenith_angle_array.data,
                viewing_azimuth_angle_array.data,
            ),
            f_band_params=f_band_params,
            model=model,
            brdf_weight=brdf_weight,
            dtype=dtype,
        ).get_band_param(),
        out_grid=grid,
        array_transform=viewing_zenith_angle_array.transform,
        in_crs=product_crs,
        nodata=0,
        resampling=Resampling.bilinear,
        keep_2d=True,
    )
    return ma.masked_where(model_params == 0.0, model_params)


def _correction_per_detector(
    product_crs: CRS,
    grid: GridProtocol,
    sun_azimuth_angle_array: np.ndarray,
    sun_zenith_angle_array: np.ndarray,
    f_band_params: ModelParameters,
    detector_footprints: ReferencedRaster,
    viewing_azimuth_per_detector: Dict[int, ReferencedRaster],
    viewing_zenith_per_detector: Dict[int, ReferencedRaster],
    model: BRDFModels = BRDFModels.default,
    brdf_weight: float = 1.0,
    smoothing_iterations: int = 10,
    dtype: DTypeLike = np.float32,
) -> ma.MaskedArray:
    """
    Run correction separately for each detector footprint.
    """
    # create output array
    model_params = ma.masked_equal(np.zeros(grid.shape, dtype=dtype), 0)

    resampled_detector_footprints = resample_from_array(
        detector_footprints,
        out_grid=grid,
        nodata=0,
        resampling=Resampling.nearest,
        keep_2d=True,
    )
    # make sure detector footprints are 2D
    if resampled_detector_footprints.ndim not in [2, 3]:
        raise ValueError(
            f"detector_footprints has to be a 2- or 3-dimensional array but has shape {detector_footprints.shape}"
        )
    if resampled_detector_footprints.ndim == 3:
        resampled_detector_footprints = resampled_detector_footprints[0]

    detector_ids: List[int] = [
        detector_id
        for detector_id in np.unique(resampled_detector_footprints)
        if detector_id != 0
    ]

    # iterate through detector footprints and calculate BRDF for each one
    for detector_id in detector_ids:
        logger.debug("run on detector %s", detector_id)

        # handle rare cases where detector geometries are available but no respective
        # angle arrays:
        if detector_id not in viewing_zenith_per_detector:  # pragma: no cover
            logger.debug("no zenith angles grid found for detector %s", detector_id)
            continue
        if detector_id not in viewing_azimuth_per_detector:  # pragma: no cover
            logger.debug("no azimuth angles grid found for detector %s", detector_id)
            continue

        # select pixels which are covered by detector
        detector_mask = np.where(
            resampled_detector_footprints == detector_id, True, False
        )

        # skip if detector footprint does not intersect with output window
        if not detector_mask.any():  # pragma: no cover
            logger.debug("detector %s does not intersect with band window", detector_id)
            continue

        # run low resolution model
        detector_model = DirectionalModels(
            angles=(
                sun_zenith_angle_array,
                sun_azimuth_angle_array,
                viewing_zenith_per_detector[detector_id].data,
                viewing_azimuth_per_detector[detector_id].data,
            ),
            f_band_params=f_band_params,
            model=model,
            brdf_weight=brdf_weight,
            dtype=dtype,
        ).get_band_param()

        # interpolate missing nodata edges and return BRDF difference model
        detector_brdf_param = ma.masked_invalid(
            fillnodata(detector_model, smoothing_iterations=smoothing_iterations)
        )

        # resample model to output resolution
        detector_brdf = resample_from_array(
            detector_brdf_param,
            out_grid=grid,
            array_transform=viewing_zenith_per_detector[detector_id].transform,
            in_crs=product_crs,
            nodata=0,
            resampling=Resampling.bilinear,
            keep_2d=True,
        )
        # merge detector stripes
        model_params[detector_mask] = detector_brdf[detector_mask]
        model_params.mask[detector_mask] = detector_brdf.mask[detector_mask]

    return model_params


def correction_values(
    s2_metadata: S2Metadata,
    band: L2ABand,
    model: BRDFModels = BRDFModels.default,
    brdf_weight: float = 1.0,
    resolution: Resolution = Resolution["60m"],
    footprints_cached_read: bool = False,
    per_detector: bool = True,
    dtype: DTypeLike = np.float32,
) -> ReferencedRaster:
    with Timer() as t:
        if per_detector:
            # Per Detector strategy:
            brdf_params = _correction_per_detector(
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
                dtype=dtype,
            )
        else:
            brdf_params = _correction_combine_detectors(
                f_band_params=L2ABandFParams[band.name].value,
                grid=s2_metadata.grid(resolution),
                product_crs=s2_metadata.crs,
                sun_azimuth_angle_array=s2_metadata.sun_angles.azimuth.raster.data,
                sun_zenith_angle_array=s2_metadata.sun_angles.zenith.raster.data,
                viewing_azimuth_angle_array=s2_metadata.viewing_incidence_angles(
                    band
                ).azimuth.merge_detectors(),
                viewing_zenith_angle_array=s2_metadata.viewing_incidence_angles(
                    band
                ).zenith.merge_detectors(),
                model=model,
                brdf_weight=brdf_weight,
                dtype=dtype,
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


def apply_correction(
    band: ma.MaskedArray,
    correction: np.ndarray,
    log10_bands_scale_flag: bool = True,
    nodata: NodataVal = 0,
) -> ma.MaskedArray:
    """
    Apply BRDF parameter to band.

    If target nodata value is 0, then the corrected band values that would become 0 are
    set to 1.

    Parameters
    ----------
    band : numpy.ma.MaskedArray
    brdf_param : numpy.ma.MaskedArray
    nodata : nodata value used to mask output

    Returns
    -------
    BRDF corrected band : numpy.ma.MaskedArray
    """
    if isinstance(band, ma.MaskedArray) and band.mask.all():  # pragma: no cover
        return band
    else:
        mask = (
            band.mask
            if isinstance(band, ma.MaskedArray)
            else np.where(band == nodata, True, False)
        )

        if log10_bands_scale_flag:
            # # Apply BRDF correction to log10 scaled Sentinel-2 data
            corrected = (
                np.log10(band.astype(np.float32, copy=False), where=band > 0)
                * correction
            ).astype(np.float32, copy=False)
            # Revert the log to linear
            corrected = (np.power(10, corrected)).astype(np.float32, copy=False)
        else:
            corrected = (band.astype(np.float32, copy=False) * correction).astype(
                np.float32, copy=False
            )

        if nodata == 0:
            return ma.masked_array(
                data=np.where(mask, 0, np.clip(corrected, 1, np.iinfo(band.dtype).max)),
                mask=mask,
            )
        else:  # pragma: no cover
            return ma.masked_array(
                data=corrected.astype(band.dtype, copy=False), mask=mask
            )
