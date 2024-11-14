from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Optional, Type

import numpy as np
from numpy.typing import DTypeLike
import numpy.ma as ma

from mapchete_eo.platforms.sentinel2.brdf.config import BRDFModels, ModelParameters

logger = logging.getLogger(__name__)


class HLSBaseBRDF:
    # Class with adapted Sentinel-2 Sentinel-Hub Normalization (Also used elsewhere)
    # Sources:
    # https://sci-hub.st/https://ieeexplore.ieee.org/document/8899868
    # https://sci-hub.st/https://ieeexplore.ieee.org/document/841980
    # https://custom-scripts.sentinel-hub.com/sentinel-2/brdf/
    # Alt GitHub: https://github.com/maximlamare/s2-normalisation
    sun_zenith: np.ndarray
    sun_azimuth: np.ndarray
    view_zenith: np.ndarray
    view_azimuth: np.ndarray
    f_band_params: ModelParameters
    processing_dtype: DTypeLike = np.float32

    theta_sun: np.ndarray
    theta_view: np.ndarray
    phi_sun: np.ndarray
    phi_view: np.ndarray
    phi: np.ndarray

    def __init__(
        self,
        sun_zenith: np.ndarray,
        sun_azimuth: np.ndarray,
        view_zenith: np.ndarray,
        view_azimuth: np.ndarray,
        f_band_params: ModelParameters,
        theta_sun: Optional[np.ndarray] = None,
        theta_view: Optional[np.ndarray] = None,
        phi: Optional[np.ndarray] = None,
        processing_dtype: DTypeLike = np.float32,
    ):
        self.sun_zenith = sun_zenith
        self.sun_azimuth = sun_azimuth
        self.view_zenith = view_zenith
        self.view_azimuth = view_azimuth
        self.f_band_params = f_band_params
        self.processing_dtype = processing_dtype

        # precalulate other values

        # Convert Degrees to Radians
        # theta is zenith angles
        self.theta_sun = np.deg2rad(self.sun_zenith) if theta_sun is None else theta_sun
        self.theta_view = (
            np.deg2rad(self.view_zenith) if theta_view is None else theta_view
        )
        # phi is azimuth angles
        self.phi_sun = np.deg2rad(self.sun_azimuth)
        self.phi_view = np.deg2rad(self.view_azimuth)

        # relative azimuth angle (in rad)
        _phi = np.abs(np.deg2rad(self.phi_sun) - np.deg2rad(self.phi_view))
        self.phi = (
            np.where(_phi > np.pi, 2 * np.pi - _phi, _phi) if phi is None else phi
        )

        # delta
        self.delta = np.sqrt(
            np.power(np.tan(self.theta_sun), 2)
            + np.power(np.tan(self.theta_view), 2)
            - 2 * np.tan(self.theta_sun) * np.tan(self.theta_view) * np.cos(self.phi)
        )

        # Air Mass
        self.masse = 1 / np.cos(self.theta_sun) + 1 / np.cos(self.theta_view)

        # xsi
        self.cos_xsi = np.cos(self.theta_sun) * np.cos(self.theta_view) + np.sin(
            self.theta_sun
        ) * np.sin(self.theta_view) * np.cos(self.phi)
        self.sin_xsi = np.sqrt(1 - np.power(self.cos_xsi, 2))
        self.xsi = np.arccos(self.cos_xsi)

        # Coeficient for "t" any natural number is good, 2 is used
        self.cos_t = np.clip(
            2
            * np.sqrt(
                np.power(self.delta, 2)
                + np.power(
                    (
                        np.tan(self.theta_sun)
                        * np.tan(self.theta_view)
                        * np.sin(self.phi)
                    ),
                    2,
                )
            )
            / (self.sec(self.theta_sun) + self.sec(self.theta_view)),
            -1,
            1,
        )

        # t
        self.t = np.clip(np.arccos(self.cos_t), -1, 1)

    def f_vol(self) -> np.ndarray:
        """Function FV Ross_Thick, V is for volume scattering (Kernel)."""
        return (
            ((np.pi / 2 - self.xsi) * self.cos_xsi + self.sin_xsi)
            / (np.cos(self.theta_sun) + np.cos(self.theta_view))
        ) - (np.pi / 4)

    def sec(self, x: np.ndarray) -> np.ndarray:
        return 1 / np.cos(x)

    #  Function FR Li-Sparse, R is for roughness (surface roughness)
    def f_roughness(self) -> np.ndarray:
        capital_o = (1 / np.pi) * (
            (self.t - np.sin(self.t) * np.cos(self.t))
            * (self.sec(self.theta_sun) + self.sec(self.theta_view))
        )

        return (
            capital_o
            - self.sec(self.theta_sun)
            - self.sec(self.theta_view)
            + (
                0.5
                * (1 + self.cos_xsi)
                * self.sec(self.theta_sun)
                * self.sec(self.theta_view)
            )
        )

    def get_model(self) -> np.ndarray:
        return (
            self.f_band_params.f_iso
            + self.f_band_params.f_geo * self.f_roughness()
            + self.f_band_params.f_vol * self.f_vol()
        )


class HLSSensorModel(HLSBaseBRDF):
    pass


class HLSSunModel(HLSBaseBRDF):
    # like sensor model, but:
    # self.theta_sun = self.sza
    # self.theta_view = np.zeros(self.theta_sun.shape)
    # self.phi = np.zeros(self.theta_sun.shape)
    pass


def get_model(
    model: BRDFModels,
    sun_zenith: np.ndarray,
    sun_azimuth: np.ndarray,
    view_zenith: np.ndarray,
    view_azimuth: np.ndarray,
    f_band_params: ModelParameters,
    sun_zenith_angles: np.ndarray,
    processing_dtype: DTypeLike = np.float32,
) -> DirectionalModels:
    if model in [BRDFModels.default, BRDFModels.HLS]:
        return HLSModel(
            sun_zenith=sun_zenith,
            sun_azimuth=sun_azimuth,
            view_zenith=view_zenith,
            view_azimuth=view_azimuth,
            f_band_params=f_band_params,
            sun_zenith_angles=sun_zenith_angles,
            processing_dtype=processing_dtype,
        )
    raise KeyError(f"unkown or not implemented model: {model}")


@dataclass
class DirectionalModels:
    sun_zenith: np.ndarray
    sun_azimuth: np.ndarray
    view_zenith: np.ndarray
    view_azimuth: np.ndarray
    f_band_params: ModelParameters
    sun_zenith_angles: np.ndarray
    processing_dtype: DTypeLike = np.float32
    sensor_model_cls: Type[HLSBaseBRDF] = HLSSensorModel
    sun_model_cls: Type[HLSBaseBRDF] = HLSSunModel

    def get_sensor_model(self):
        return HLSSensorModel(
            sun_zenith=self.sun_zenith,
            sun_azimuth=self.sun_azimuth,
            view_zenith=self.view_zenith,
            view_azimuth=self.view_azimuth,
            f_band_params=self.f_band_params,
            processing_dtype=self.processing_dtype,
        ).get_model()

    def get_sun_model(self):
        # Keep the SunModel values as is without weighting
        return HLSSunModel(
            sun_zenith=self.sun_zenith,
            sun_azimuth=self.sun_azimuth,
            view_zenith=self.view_zenith,
            view_azimuth=self.view_azimuth,
            theta_sun=self.sun_zenith_angles,
            theta_view=np.zeros(self.sun_zenith_angles.shape),
            phi=np.zeros(self.sun_zenith_angles.shape),
            f_band_params=self.f_band_params,
            processing_dtype=self.processing_dtype,
        ).get_model()

    def get_band_param(self) -> ma.MaskedArray:
        out_param_arr = self.get_sun_model() / self.get_sensor_model()
        return ma.masked_array(
            data=out_param_arr.astype(self.processing_dtype, copy=False),
            mask=np.where(out_param_arr == 0, True, False).astype(bool, copy=False),
        )


class HLSModel(DirectionalModels):
    """Directional model."""

    sensor_model_cls: Type[HLSBaseBRDF] = HLSSensorModel
    sun_model_cls: Type[HLSBaseBRDF] = HLSSunModel
