import logging
from typing import List

from mapchete import Timer
from mapchete.io.raster import ReferencedRaster, resample_from_array
from mapchete.protocols import GridProtocol
from mapchete.types import NodataVal
import numpy as np
import numpy.ma as ma
from numpy.typing import DTypeLike
from rasterio.enums import Resampling
from rasterio.fill import fillnodata

from mapchete_eo.exceptions import BRDFError
from mapchete_eo.platforms.sentinel2.brdf.models import BRDFModels, get_model
from mapchete_eo.platforms.sentinel2.metadata_parser import S2Metadata
from mapchete_eo.platforms.sentinel2.types import (
    L2ABand,
    Resolution,
)

logger = logging.getLogger(__name__)


def _correction_combine_detectors(
    s2_metadata: S2Metadata,
    band: L2ABand,
    out_grid: GridProtocol,
    model: BRDFModels = BRDFModels.HLS,
    dtype: DTypeLike = np.float32,
) -> ma.MaskedArray:
    """
    Run correction using combined angle masks of all
    """
    return resample_from_array(
        get_model(
            model=model, s2_metadata=s2_metadata, band=band, processing_dtype=dtype
        ).calculate(),
        out_grid=out_grid,
        nodata=0,
        resampling=Resampling.bilinear,
        keep_2d=True,
    )


def _correction_per_detector(
    s2_metadata: S2Metadata,
    band: L2ABand,
    out_grid: GridProtocol,
    model: BRDFModels = BRDFModels.HLS,
    smoothing_iterations: int = 10,
    dtype: DTypeLike = np.float32,
    footprints_cached_read: bool = True,
) -> ma.MaskedArray:
    """
    Run correction separately for each detector footprint.
    """
    # create output array
    model_params = ma.masked_equal(np.zeros(out_grid.shape, dtype=dtype), 0)

    # get detector footprints
    detector_footprints = s2_metadata.detector_footprints(
        band, cached_read=footprints_cached_read
    )
    resampled_detector_footprints = resample_from_array(
        detector_footprints,
        out_grid=out_grid,
        nodata=0,
        resampling=Resampling.nearest,
        keep_2d=True,
    )
    if resampled_detector_footprints.ndim not in [2, 3]:
        raise ValueError(
            f"detector_footprints has to be a 2- or 3-dimensional array but has shape {detector_footprints.shape}"
        )
    if resampled_detector_footprints.ndim == 3:
        resampled_detector_footprints = resampled_detector_footprints[0]

    # determine available detector IDs
    detector_ids: List[int] = [
        detector_id
        for detector_id in np.unique(resampled_detector_footprints)
        if detector_id != 0
    ]

    # get viewing angle arrays per detector
    viewing_azimuth_per_detector = s2_metadata.viewing_incidence_angles(
        band
    ).azimuth.detectors
    viewing_zenith_per_detector = s2_metadata.viewing_incidence_angles(
        band
    ).zenith.detectors

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
        model_values = get_model(
            model=model,
            s2_metadata=s2_metadata,
            band=band,
            detector_id=detector_id,
            processing_dtype=dtype,
        ).calculate()

        # interpolate missing nodata edges and return BRDF difference model
        detector_brdf_param = ma.masked_invalid(
            fillnodata(model_values.data, smoothing_iterations=smoothing_iterations)
        )

        # resample model to output resolution
        detector_brdf = resample_from_array(
            detector_brdf_param,
            out_grid=out_grid,
            array_transform=model_values.transform,
            in_crs=model_values.crs,
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
    model: BRDFModels = BRDFModels.HLS,
    resolution: Resolution = Resolution["60m"],
    footprints_cached_read: bool = False,
    per_detector: bool = True,
    dtype: DTypeLike = np.float32,
) -> ReferencedRaster:
    """Calculate BRDF correction values.

    Calculation is always done on original product CRS, but the resolution
    can be defined.
    """
    with Timer() as t:
        if per_detector:
            # Per Detector strategy:
            brdf_params = _correction_per_detector(
                s2_metadata=s2_metadata,
                band=band,
                out_grid=s2_metadata.grid(resolution),
                model=model,
                dtype=dtype,
                footprints_cached_read=footprints_cached_read,
            )
        else:
            brdf_params = _correction_combine_detectors(
                s2_metadata=s2_metadata,
                band=band,
                out_grid=s2_metadata.grid(resolution),
                model=model,
                dtype=dtype,
            )
    logger.debug(
        f"BRDF for product {s2_metadata.product_id} band {band.name} calculated in {str(t)}"
    )
    if brdf_params.mask.all():  # pragma: no cover
        raise BRDFError(f"BRDF grid array for {s2_metadata.product_id} is empty!")
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
    log10_bands_scale: bool = False,
    correction_weight: float = 1.0,
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

        if correction_weight != 1.0:
            logger.debug("apply weight to correction")
            # a correction_weight value of >1 should increase the correction, whereas a
            # value <1 should decrease the correction
            correction = 1 - (1 - correction) * correction_weight

        if log10_bands_scale:
            # # Apply BRDF correction to log10 scaled Sentinel-2 data
            corrected = (
                np.log10(band.astype(np.float32, copy=False), where=band > 0)
                * correction
            ).astype(np.float32, copy=False)
            # Revert the log to linear
            corrected = (np.power(10, corrected)).astype(np.float32, copy=False)
        else:
            corrected = (band.astype(np.float32, copy=False) * correction).astype(
                band.dtype, copy=False
            )

        if nodata == 0:
            return ma.masked_array(
                data=np.where(
                    mask,
                    0,
                    np.clip(corrected, 1, np.iinfo(band.dtype).max).astype(
                        band.dtype, copy=False
                    ),
                ),
                mask=mask,
            )
        else:  # pragma: no cover
            return ma.masked_array(
                data=corrected.astype(band.dtype, copy=False), mask=mask
            )
