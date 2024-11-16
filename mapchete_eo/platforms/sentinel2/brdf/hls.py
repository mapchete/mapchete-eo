"""
Legacy implementation from before 2024.
"""

from __future__ import annotations
from typing import Optional, Tuple
import numpy as np
import numpy.ma as ma
from numpy.typing import DTypeLike

from mapchete_eo.platforms.sentinel2.brdf.protocols import (
    BRDFModelProtocol,
)
from mapchete_eo.platforms.sentinel2.brdf.config import L2ABandFParams, ModelParameters
from mapchete_eo.platforms.sentinel2.brdf.sun_angle_arrays import get_sun_zenith_angles
from mapchete_eo.platforms.sentinel2.metadata_parser import S2Metadata
from mapchete_eo.platforms.sentinel2.types import L2ABand


class HLSBaseBRDF:
    """Base class for sensor and sun models."""

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

    def calculate(self) -> np.ndarray:
        return (
            self.f_band_params.f_iso
            + self.f_band_params.f_geo * self.f_roughness()
            + self.f_band_params.f_vol * self.f_vol()
        )


class HLSSensorModel(HLSBaseBRDF, BRDFModelProtocol):
    @staticmethod
    def from_s2metadata(
        s2_metadata: S2Metadata,
        band: L2ABand,
        detector_id: Optional[int] = None,
        processing_dtype: DTypeLike = np.float32,
    ) -> HLSSensorModel:
        # NOTE: this method is just here for the protocol & some debugging
        view_zenith, view_azimuth = _get_viewing_angles(
            s2_metadata=s2_metadata, band=band, detector_id=detector_id
        )
        return HLSSensorModel(
            sun_zenith=s2_metadata.sun_angles.zenith.raster.data,
            sun_azimuth=s2_metadata.sun_angles.azimuth.raster.data,
            view_zenith=view_zenith,
            view_azimuth=view_azimuth,
            f_band_params=L2ABandFParams[band.name].value,
            processing_dtype=processing_dtype,
        )


class HLSSunModel(HLSBaseBRDF, BRDFModelProtocol):
    # like sensor model, but:
    # self.theta_sun = self.sza
    # self.theta_view = np.zeros(self.theta_sun.shape)
    # self.phi = np.zeros(self.theta_sun.shape)

    @staticmethod
    def from_s2metadata(
        s2_metadata: S2Metadata,
        band: L2ABand,
        detector_id: Optional[int] = None,
        processing_dtype: DTypeLike = np.float32,
    ) -> HLSSunModel:
        # NOTE: this method is just here for the protocol & some debugging
        view_zenith, view_azimuth = _get_viewing_angles(
            s2_metadata=s2_metadata, band=band, detector_id=detector_id
        )
        sun_zenith_angles = get_sun_zenith_angles(s2_metadata)
        return HLSSunModel(
            sun_zenith=s2_metadata.sun_angles.zenith.raster.data,
            sun_azimuth=s2_metadata.sun_angles.azimuth.raster.data,
            view_zenith=view_zenith,
            view_azimuth=view_azimuth,
            theta_sun=sun_zenith_angles,
            theta_view=np.zeros(sun_zenith_angles.shape),
            phi=np.zeros(sun_zenith_angles.shape),
            f_band_params=L2ABandFParams[band.name].value,
            processing_dtype=processing_dtype,
        )


class HLS(BRDFModelProtocol):
    """Directional model."""

    sun_zenith: np.ndarray
    sun_azimuth: np.ndarray
    view_zenith: np.ndarray
    view_azimuth: np.ndarray
    f_band_params: ModelParameters
    processing_dtype: DTypeLike = np.float32

    def __init__(
        self,
        s2_metadata: S2Metadata,
        band: L2ABand,
        detector_id: Optional[int] = None,
        processing_dtype: DTypeLike = np.float32,
    ):
        self.sun_zenith = s2_metadata.sun_angles.zenith.raster.data
        self.sun_azimuth = s2_metadata.sun_angles.azimuth.raster.data
        self.view_zenith, self.view_azimuth = _get_viewing_angles(
            s2_metadata=s2_metadata, band=band, detector_id=detector_id
        )
        self.f_band_params = L2ABandFParams[band.name].value
        self.processing_dtype = processing_dtype
        self.sun_zenith_angles = get_sun_zenith_angles(s2_metadata)

    def sensor_model(self) -> BRDFModelProtocol:
        return HLSSensorModel(
            sun_zenith=self.sun_zenith,
            sun_azimuth=self.sun_azimuth,
            view_zenith=self.view_zenith,
            view_azimuth=self.view_azimuth,
            f_band_params=self.f_band_params,
            processing_dtype=self.processing_dtype,
        )

    def sun_model(self) -> BRDFModelProtocol:
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
        )

    def calculate(self) -> ma.MaskedArray:
        out_param_arr = self.sun_model().calculate() / self.sensor_model().calculate()
        return ma.masked_array(
            data=out_param_arr.astype(self.processing_dtype, copy=False),
            mask=np.where(out_param_arr == 0, True, False),
        )

    @staticmethod
    def from_s2metadata(
        s2_metadata: S2Metadata,
        band: L2ABand,
        detector_id: Optional[int] = None,
        processing_dtype: DTypeLike = np.float32,
    ) -> HLS:
        return HLS(
            s2_metadata=s2_metadata,
            band=band,
            detector_id=detector_id,
            processing_dtype=processing_dtype,
        )


def _get_viewing_angles(
    s2_metadata: S2Metadata, band: L2ABand, detector_id: Optional[int] = None
) -> Tuple[np.ndarray, np.ndarray]:
    """Get viewing angles for single detector or for all detectors."""
    if detector_id is not None:
        view_zenith = (
            s2_metadata.viewing_incidence_angles(band)
            .zenith.detectors[detector_id]
            .data
        )
        view_azimuth = (
            s2_metadata.viewing_incidence_angles(band)
            .azimuth.detectors[detector_id]
            .data
        )
    else:
        view_zenith = (
            s2_metadata.viewing_incidence_angles(band).zenith.merge_detectors().data
        )
        view_azimuth = (
            s2_metadata.viewing_incidence_angles(band).azimuth.merge_detectors().data
        )
    return (view_zenith, view_azimuth)
