import logging
from typing import Tuple, Union

import numpy as np
import numpy.ma as ma
from affine import Affine
from mapchete.io.raster import ReferencedRaster
from rasterio.crs import CRS
from rasterio.fill import fillnodata
from tilematrix import Shape

from mapchete_eo.array.resampling import resample_array
from mapchete_eo.brdf.config import BRDFModels

logger = logging.getLogger(__name__)


class DirectionalModels:
    def __init__(
        self,
        angles,
        f_band_params,
        sza,
        model=BRDFModels.default,
        upscale_factor=10000,
        sun_model_flag=False,
    ):
        self.angles = angles
        self.f_band_params = f_band_params
        self.sza = sza
        self.model = BRDFModels(model)
        self.upscale_factor = upscale_factor
        self.sun_model_flag = sun_model_flag

    def get_model(self):
        if self.sun_model_flag is True:
            return SunModel(
                self.angles, self.f_band_params, self.sza, self.model
            ).get_model()

        else:
            return SensorModel(
                self.angles, self.f_band_params, self.sza, self.model
            ).get_model()

    def get_band_param(self):
        sensor_model = SensorModel(
            self.angles, self.f_band_params, self.sza, self.model
        ).get_model()

        sun_model = SunModel(
            self.angles, self.f_band_params, self.sza, model=self.model
        ).get_model()

        out_param_arr = sun_model / sensor_model

        return ma.masked_array(
            data=out_param_arr,
            mask=np.where(out_param_arr == 0, True, False).astype(bool, copy=False),
        ).astype(np.float32, copy=False)

    def get_corrected_band_reflectance(self, band):
        return get_corrected_band_reflectance(band, self.get_band_param())


class BaseBRDF:
    # Class with adapted sen2agri model computation
    # https://userpages.umbc.edu/~martins/PHYS650/maignan%20brdf.pdf
    # http://www.esa-sen2agri.org/wp-content/uploads/resources/technical-documents/Sen2Agri_DDF_v1.2_ATBDComposite.pdf
    def __init__(self, angles, f_band_params, sza, model="sen2agri"):
        self.model = model
        # angles should have a form of tuple where:
        # sun_zenith, sun azimuth, view_zenith, view_azimuth
        theta_sun, phi_sun, theta_view, phi_view = angles
        # Convert Degrees to Radians
        # theta is zenith angles
        # phi is azimuth angles
        self.theta_sun = theta_sun * np.pi / 180
        self.theta_view = theta_view * np.pi / 180
        self.phi = (phi_sun - phi_view) * np.pi / 180
        self.phi = np.where(self.phi < 0, self.phi + 2 * np.pi, self.phi)

        # (Modis based) Parameters for the linear model
        self.f_band_params = f_band_params

        # Constant sun angle
        if isinstance(sza, (float, int)):
            self.sza = np.full(self.theta_sun.shape, sza)
        elif isinstance(sza, np.ndarray):
            self.sza = sza
        else:
            raise TypeError("sza must either be a number or a numpy array")

        self.xsi_0 = np.full(self.theta_sun.shape, 1.5 * np.pi / 180)

    # Get delta
    def delta(self):
        delta = np.sqrt(
            np.power(np.tan(self.theta_sun), 2)
            + np.power(np.tan(self.theta_view), 2)
            - 2 * np.tan(self.theta_sun) * np.tan(self.theta_view) * np.cos(self.phi)
        )
        return delta

    # Air Mass
    def masse(self):
        masse = 1 / np.cos(self.theta_sun) + 1 / np.cos(self.theta_view)
        return masse

    # Get xsi
    def cos_xsi(self):
        cos_xsi = np.cos(self.theta_sun) * np.cos(self.theta_view) + np.sin(
            self.theta_sun
        ) * np.sin(self.theta_view) * np.cos(self.phi)
        return cos_xsi

    def sin_xsi(self):
        x = self.cos_xsi()
        sin_xsi = np.sqrt(1 - np.power(x, 2))
        return sin_xsi

    def xsi(self):
        xsi = np.arccos(self.cos_xsi())
        return xsi

    # Function t
    def cos_t(self):
        trig = np.tan(self.theta_sun) * np.tan(self.theta_view) * np.sin(self.phi)
        d = self.delta()
        # Coeficient for "t" any natural number is good, 1 or 2 are used
        coef = 1
        cos_t = coef / self.masse() * np.sqrt(np.power(d, 2) + np.power(trig, 2))
        cos_t = np.where(cos_t > 1, 1, cos_t)
        cos_t = np.where(cos_t < -1, -1, cos_t)
        return cos_t

    def sin_t(self):
        x = self.cos_t()
        sin_t = np.sqrt(1 - np.power(x, 2))
        return sin_t

    def t(self):
        t = np.arccos(self.cos_t())
        return t

    # Function FV Ross_Thick, V is for volume scattering (Kernel)
    def fv(self):
        fv = (self.masse() / np.pi) * (
            (self.t() - self.sin_t() * self.cos_t() - np.pi)
            + (
                (1 + self.cos_xsi())
                / (2 * np.cos(self.theta_sun) * np.cos(self.theta_view))
            )
        )
        return fv

    #  Function FR Li-Sparse, R is for roughness (surface roughness)
    def fr(self):
        fr = None
        a = 1 / (np.cos(self.theta_sun) + np.cos(self.theta_view))
        if self.model == "sen2agri" or self.model == "combined":
            # sen2agri formula
            fr = 4 / (3 * np.pi) * a * (
                (np.pi / 2 - self.xsi()) * self.cos_xsi() + self.sin_xsi()
            ) * (1 + 1 / (1 / self.xsi() / self.xsi_0)) - (1 / 3)
        if "HLS".lower() in self.model.lower():
            # HLS formula
            # https://userpages.umbc.edu/~martins/PHYS650/maignan%20brdf.pdf
            fr = 4 / (3 * np.pi) * a * (
                (np.pi / 2 - self.xsi()) * self.cos_xsi() + self.sin_xsi()
            ) - (1 / 3)

        return fr

    def get_model(self):
        model_value = None

        if self.model == "HLS" or self.model == "combined":
            # Standard HLS model
            model_value = (
                self.f_band_params[0]
                + self.f_band_params[2] * self.fv()
                + self.f_band_params[1] * self.fr()
            )

        if self.model == "sen2agri":
            # Sen2agri nomalization
            # http://www.esa-sen2agri.org/wp-content/uploads/resources/technical-documents/Sen2Agri_DDF_v1.2_ATBDComposite.pdf
            model_value = (
                1
                + self.f_band_params[2] * self.fv()
                + self.f_band_params[1] * self.fr()
            )

        if self.model == "HLS_alt":
            # Alt normalization as in 2.2.2 of:
            # It is a formula that aims to decompose the HLS harmonization
            # We just use it as an alt formula for BRDF as it is similar to
            # the sen2agri approach in some ways
            # https://www.google.com/url?sa=t&rct=j&q=&esrc=s&source=web&cd=&cad=rja&uact=8&ved=2ahUKEwjijoqF6abrAhXJfMAKHanQC28QFjAAegQIAxAB&url=https%3A%2F%2Fwww.mdpi.com%2F2072-4292%2F11%2F6%2F632%2Fpdf&usg=AOvVaw0gCUSpFzULY3ZVICIXvnBa
            model_value = self.f_band_params[0] * (
                1
                + self.f_band_params[2] / self.f_band_params[0] * self.fv()
                + self.f_band_params[1] / self.f_band_params[0] * self.fr()
            )
        return model_value


class SensorModel(BaseBRDF):
    def __init__(self, angles, f_band_params, sza, model="sen2agri"):
        super().__init__(angles, f_band_params, sza, model)


class SunModel(BaseBRDF):
    def __init__(self, angles, f_band_params, sza, model="sen2agri"):
        super().__init__(angles, f_band_params, sza, model)
        self.theta_view = np.zeros(self.theta_sun.shape)
        self.theta_sun = self.sza
        self.phi = np.zeros(self.theta_sun.shape)


def get_corrected_band_reflectance(band, brdf_param, nodata=0):
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
        corrected = (band * brdf_param).astype(band.dtype, copy=False)
        if nodata == 0:
            return ma.masked_array(
                data=np.where(mask, 0, np.clip(corrected, 1, np.iinfo(band.dtype).max)),
                mask=mask,
            )
        else:  # pragma: no cover
            return ma.masked_array(data=corrected, mask=mask).astype(
                band.dtype, copy=False
            )


def get_brdf_param(
    out_shape: Shape,
    out_transform: Affine,
    product_crs: CRS,
    sun_azimuth_angle_array: np.ndarray,
    sun_zenith_angle_array: np.ndarray,
    detector_footprints: ReferencedRaster,
    viewing_zenith: dict,
    viewing_azimuth: dict,
    sun_zenith_angle: float,
    f_band_params: Tuple[float, float, float],
    out_crs: Union[CRS, None] = None,
    model: BRDFModels = BRDFModels.default,
    smoothing_iterations: int = 10,
) -> ma.MaskedArray:
    """
    Return BRDF parameters.
    """
    out_crs = out_crs or product_crs
    # create output array
    model_params = ma.masked_equal(np.zeros(out_shape, dtype=np.float32), 0)

    detector_footprints = resample_array(
        detector_footprints,
        nodata=0,
        dst_transform=out_transform,
        dst_crs=out_crs,
        dst_shape=out_shape,
        resampling="nearest",
    )[0]
    detector_ids = [x for x in np.unique(detector_footprints.data) if x != 0]

    # iterate through detector footprints and calculate BRDF for each one
    for detector_id in detector_ids:
        logger.debug(f"run on detector {detector_id}")

        # handle rare cases where detector geometries are available but no respective
        # angle arrays:
        if detector_id not in viewing_zenith:  # pragma: no cover
            logger.debug(f"no zenith angles grid found for detector {detector_id}")
            continue
        if detector_id not in viewing_azimuth:  # pragma: no cover
            logger.debug(f"no azimuth angles grid found for detector {detector_id}")
            continue

        # select pixels which are covered by detector
        detector_mask = np.where(detector_footprints == detector_id, True, False)

        # skip if detector footprint does not intersect with output window
        if not detector_mask.any():  # pragma: no cover
            logger.debug(f"detector {detector_id} does not intersect with band window")
            continue

        # run low resolution model
        detector_model = DirectionalModels(
            angles=(
                sun_zenith_angle_array["raster"].data,
                sun_azimuth_angle_array["raster"].data,
                viewing_zenith[detector_id]["raster"].data,
                viewing_azimuth[detector_id]["raster"].data,
            ),
            f_band_params=f_band_params,
            sza=sun_zenith_angle,
            model=model,
        ).get_band_param()

        # interpolate missing nodata edges and return BRDF difference model
        detector_brdf_param = ma.masked_invalid(
            fillnodata(detector_model, smoothing_iterations=smoothing_iterations)
        )

        # resample model to output resolution
        detector_brdf = resample_array(
            detector_brdf_param,
            in_transform=viewing_zenith[detector_id]["raster"].transform,
            in_crs=product_crs,
            nodata=0,
            dst_transform=out_transform,
            dst_crs=out_crs,
            dst_shape=out_shape,
            resampling="bilinear",
        )
        # merge detector stripes
        model_params[detector_mask] = detector_brdf[detector_mask]
        model_params.mask[detector_mask] = detector_brdf.mask[detector_mask]

    return model_params


def apply_brdf_correction(
    band=None,
    band_crs=None,
    band_transform=None,
    product_crs=None,
    sun_azimuth_angle_array=None,
    sun_zenith_angle_array=None,
    detector_footprints=None,
    viewing_zenith=None,
    viewing_azimuth=None,
    sun_zenith_angle=None,
    f_band_params=None,
    model=BRDFModels.default,
    smoothing_iterations=10,
):
    """
    Return BRDF corrected band reflectance.

    Parameters
    ----------
    band : np.ndarray
        Band reflectance.
    band_crs : str
        CRS of band.
    band_transform : Affine
        Band Affine object.
    product_crs : str
        CRS of product.
    sun_azimuth_angle_array : dict
        Dictionary of Azimuth angle grids.
    sun_zenith_angle_array : dict
        Dictionary of Zenith angle grids.
    detector_footprints : dict
        Detector footprints by detector ID.
    viewing_zenith : dict
        Dictionary of Zenith incidence angles by detector ID.
    viewing_azimuth : dict
        Dictionary of Zenith incidence angles by detector ID.
    sun_zenith_angle : float
        Constant sun angle for product.
    model : str
        BRDF model to run.
    smoothing_iterations : int
        Smoothness of interpolated angle grids
    """
    if not isinstance(band, ma.MaskedArray):  # pragma: no cover
        raise TypeError("input band must be a masked array")
    for param, name in [
        (band_transform, "band_transform"),
        (product_crs, "product_crs"),
        (sun_azimuth_angle_array, "sun_azimuth_angle"),
        (sun_zenith_angle_array, "sun_zenith_angle"),
        (detector_footprints, "detector_footprints"),
        (viewing_zenith, "viewing_zenith"),
        (viewing_azimuth, "viewing_azimuth"),
        (sun_zenith_angle, "sun_zenith_angle"),
        (f_band_params, "f_band_params"),
    ]:
        if param is None:  # pragma: no cover
            raise ValueError(f"{name} must be provided")

    return get_corrected_band_reflectance(
        band=band,
        brdf_param=get_brdf_param(
            out_shape=band.shape,
            out_transform=band_transform,
            out_crs=band_crs,
            product_crs=product_crs,
            sun_azimuth_angle_array=sun_azimuth_angle_array,
            sun_zenith_angle_array=sun_zenith_angle_array,
            detector_footprints=detector_footprints,
            viewing_zenith=viewing_zenith,
            viewing_azimuth=viewing_azimuth,
            sun_zenith_angle=sun_zenith_angle,
            f_band_params=f_band_params,
            model=model,
            smoothing_iterations=smoothing_iterations,
        ),
    )
