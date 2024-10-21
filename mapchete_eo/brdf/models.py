import logging
from typing import Dict, Tuple

import numpy as np
from numpy.typing import DTypeLike
import numpy.ma as ma
from mapchete.io.raster import ReferencedRaster, resample_from_array
from mapchete.protocols import GridProtocol
from mapchete.types import NodataVal
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.fill import fillnodata

from mapchete_eo.brdf.config import BRDFModels

logger = logging.getLogger(__name__)


class DirectionalModels:
    def __init__(
        self,
        angles: Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
        f_band_params: Tuple[float, float, float],
        model=BRDFModels.default,
        brdf_weight: float = 1.0,
        dtype: DTypeLike = np.float32,
    ):
        self.angles = angles
        self.f_band_params = f_band_params
        self.model = BRDFModels(model)
        if self.model == BRDFModels.none:
            raise ValueError("model cannot be BRDFModels.none")
        self.brdf_weight = brdf_weight
        self.dtype = dtype

    def get_sensor_model(self):
        return SensorModel(
            self.angles, self.f_band_params, self.model, self.brdf_weight
        ).get_model()

    def get_sun_model(self):
        # Keep the SunModel values as is without weighting
        return SunModel(
            self.angles, self.f_band_params, self.model, brdf_weight=1.0
        ).get_model()

    def get_band_param(self):
        sensor_model = SensorModel(
            self.angles, self.f_band_params, self.model, self.brdf_weight
        ).get_model()

        # Keep the SunModel values as is without weighting
        sun_model = SunModel(
            self.angles, self.f_band_params, self.model, brdf_weight=1.0
        ).get_model()

        # if self.brdf_weight != 1.0:
        #     out_param_arr = sun_model / (sensor_model * (self.brdf_weight * self.f_band_params[0]))
        # else:
        out_param_arr = sun_model / sensor_model

        return ma.masked_array(
            data=out_param_arr,
            mask=np.where(out_param_arr == 0, True, False).astype(bool, copy=False),
        ).astype(self.dtype, copy=False)

    def get_corrected_band_reflectance(self, band):
        return get_corrected_band_reflectance(band, self.get_band_param())


class BaseBRDF:
    # Class with adapted Sentinel-2 Sentinel-Hub Normalization (Also used elsewhere)
    # Sources:
    # https://sci-hub.st/https://ieeexplore.ieee.org/document/8899868
    # https://sci-hub.st/https://ieeexplore.ieee.org/document/841980
    # https://custom-scripts.sentinel-hub.com/sentinel-2/brdf/
    # Alt GitHub: https://github.com/maximlamare/s2-normalisation
    def __init__(
        self,
        angles: Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
        f_band_params: Tuple[float, float, float],
        model: str = "HLS",
        brdf_weight: float = 1.0,
    ):
        self.model = model
        # angles should have a form of tuple where:
        # sun_zenith, sun azimuth, view_zenith, view_azimuth
        theta_sun, phi_sun, theta_view, phi_view = angles
        # Convert Degrees to Radians
        # theta is zenith angles
        # phi is azimuth angles
        self.theta_sun = np.deg2rad(theta_sun)
        self.theta_view = np.deg2rad(theta_view)

        self.phi_sun = np.deg2rad(phi_sun)
        self.phi_view = np.deg2rad(phi_view)
        self.phi = np.deg2rad(np.abs(self.phi_sun - self.phi_view))

        # (Modis based) Parameters for the linear model
        self.f_band_params = f_band_params
        self.brdf_weight = brdf_weight

    # Get delta
    def delta(self) -> np.ndarray:
        delta = np.sqrt(
            np.power(np.tan(self.theta_sun), 2)
            + np.power(np.tan(self.theta_view), 2)
            - 2 * np.tan(self.theta_sun) * np.tan(self.theta_view) * np.cos(self.phi)
        )
        return delta

    # Air Mass
    def masse(self) -> np.ndarray:
        masse = 1 / np.cos(self.theta_sun) + 1 / np.cos(self.theta_view)
        return masse

    # Get xsi
    def cos_xsi(self) -> np.ndarray:
        cos_xsi = np.cos(self.theta_sun) * np.cos(self.theta_view) + np.sin(
            self.theta_sun
        ) * np.sin(self.theta_view) * np.cos(self.phi)
        return cos_xsi

    def sin_xsi(self) -> np.ndarray:
        x = self.cos_xsi()
        sin_xsi = np.sqrt(1 - np.power(x, 2))
        return sin_xsi

    def xsi(self) -> np.ndarray:
        xsi = np.arccos(self.cos_xsi())
        return xsi

    # Function t
    def cos_t(self) -> np.ndarray:
        def sec(x):
            return 1 / np.cos(x)

        # Coeficient for "t" any natural number is good, 2 is used
        cos_t = (
            2
            * np.sqrt(
                np.power(self.delta(), 2)
                + np.power(
                    (
                        np.tan(self.theta_sun)
                        * np.tan(self.theta_view)
                        * np.sin(self.phi)
                    ),
                    2,
                )
            )
            / (sec(self.theta_sun) + sec(self.theta_view))
        )

        cos_t = np.where(cos_t > 1, 1, cos_t)
        cos_t = np.where(cos_t < -1, -1, cos_t)
        return cos_t

    def t(self) -> np.ndarray:
        t = np.arccos(self.cos_t())
        return t

    # Function FV Ross_Thick, V is for volume scattering (Kernel)
    def fv(self) -> np.ndarray:
        fv = (
            ((np.pi / 2 - self.xsi()) * self.cos_xsi() + self.sin_xsi())
            / (np.cos(self.theta_sun) + np.cos(self.theta_view))
        ) - (np.pi / 4)

        return fv

    #  Function FR Li-Sparse, R is for roughness (surface roughness)
    def fr(self) -> np.ndarray:
        def sec(x):
            return 1 / np.cos(x)

        capital_o = (1 / np.pi) * (
            (self.t() - np.sin(self.t()) * np.cos(self.t()))
            * (sec(self.theta_sun) + sec(self.theta_view))
        )

        fr = (
            capital_o
            - sec(self.theta_sun)
            - sec(self.theta_view)
            + (0.5 * (1 + self.cos_xsi()) * sec(self.theta_sun) * sec(self.theta_view))
        )

        return fr

    def get_model(self) -> np.ndarray:
        if self.model == "HLS" or self.model == "default":
            # Standard (HLS) BRDF model
            if self.brdf_weight != 1.0:
                model_value = (
                    self.f_band_params[0]
                    + self.f_band_params[2] * self.fv() / self.brdf_weight
                    + self.f_band_params[1] * self.fr() / self.brdf_weight
                )
            else:
                model_value = (
                    self.f_band_params[0]
                    + self.f_band_params[2] * self.fv()
                    + self.f_band_params[1] * self.fr()
                )
        return model_value


class SensorModel(BaseBRDF):
    def __init__(self, angles, f_band_params, model="HLS", brdf_weight=1.0):
        super().__init__(angles, f_band_params, model, brdf_weight)


class SunModel(BaseBRDF):
    def __init__(self, angles, f_band_params, model="HLS", brdf_weight=1.0):
        super().__init__(angles, f_band_params, model, brdf_weight)
        self.theta_view = np.zeros(self.theta_sun.shape)


def get_corrected_band_reflectance(
    band: ma.MaskedArray,
    correction: np.ndarray,
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

        # # Apply BRDF correction to arcsinh scaled Sentinel-2 data
        # Arcsinh:
        # The arcsinh function also compresses large values, but it grows more uniformly across the range of inputs.
        # It is less sensitive to changes in small values compared to log10.
        # For small values (close to zero), arcsinh behaves like the input, making it less extreme than log10.
        corrected = (
            np.arcsinh(band.astype(np.float32, copy=False)) * correction
        ).astype(np.float32, copy=False)
        # Revert the log to linear
        corrected = np.sinh(corrected).astype(np.float32, copy=False)

        if nodata == 0:
            return ma.masked_array(
                data=np.where(mask, 0, np.clip(corrected, 1, np.iinfo(band.dtype).max)),
                mask=mask,
            )
        else:  # pragma: no cover
            return ma.masked_array(
                data=corrected.astype(band.dtype, copy=False), mask=mask
            )


def get_brdf_param(
    product_crs: CRS,
    grid: GridProtocol,
    sun_azimuth_angle_array: np.ndarray,
    sun_zenith_angle_array: np.ndarray,
    detector_footprints: ReferencedRaster,
    viewing_zenith_per_detector: Dict[int, ReferencedRaster],
    viewing_azimuth_per_detector: Dict[int, ReferencedRaster],
    f_band_params: Tuple[float, float, float],
    model: BRDFModels = BRDFModels.default,
    brdf_weight: float = 1.0,
    smoothing_iterations: int = 10,
    dtype: DTypeLike = np.float32,
) -> ma.MaskedArray:
    """
    Return BRDF parameters.
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

    detector_ids = [
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
                sun_zenith_angle_array.data,
                sun_azimuth_angle_array.data,
                viewing_zenith_per_detector[detector_id].data,
                viewing_azimuth_per_detector[detector_id].data,
            ),
            f_band_params=f_band_params,
            model=model,
            brdf_weight=brdf_weight,
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
