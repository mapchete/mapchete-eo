"""
Legacy implementation from before 2024.
"""

from __future__ import annotations
from typing import Optional, Tuple

from affine import Affine
from mapchete.io.raster import ReferencedRaster
from mapchete.types import CRSLike
import numpy as np
from numpy.typing import DTypeLike

from mapchete_eo.platforms.sentinel2.brdf.protocols import (
    BRDFModelProtocol,
)
from mapchete_eo.platforms.sentinel2.brdf.config import L2ABandFParams, ModelParameters
from mapchete_eo.platforms.sentinel2.brdf.sun_angle_arrays import get_sun_zenith_angles
from mapchete_eo.platforms.sentinel2.metadata_parser import S2Metadata
from mapchete_eo.platforms.sentinel2.types import L2ABand


class HLSBaseModel:
    """Base class for sensor and sun models."""

    # Class with adapted Sentinel-2 Sentinel-Hub Normalization (Also used elsewhere)
    # Sources:
    # https://sci-hub.st/https://ieeexplore.ieee.org/document/8899868
    # https://sci-hub.st/https://ieeexplore.ieee.org/document/841980
    # https://custom-scripts.sentinel-hub.com/sentinel-2/brdf/
    # Alt GitHub: https://github.com/maximlamare/s2-normalisation
    sun_zenith_radian: np.ndarray
    sun_azimuth_radian: np.ndarray
    view_zenith_radian: np.ndarray
    view_azimuth_radian: np.ndarray
    f_band_params: ModelParameters
    relative_azimuth_angle_radian: np.ndarray
    processing_dtype: DTypeLike = np.float32

    def __init__(
        self,
        sun_zenith_radian: np.ndarray,
        sun_azimuth_radian: np.ndarray,
        view_zenith_radian: np.ndarray,
        view_azimuth_radian: np.ndarray,
        f_band_params: ModelParameters,
        relative_azimuth_angle_radian: Optional[np.ndarray] = None,
        processing_dtype: DTypeLike = np.float32,
    ):
        self.sun_zenith_radian = sun_zenith_radian
        self.sun_azimuth_radian = sun_azimuth_radian
        self.view_zenith_radian = view_zenith_radian
        self.view_azimuth_radian = view_azimuth_radian
        self.f_band_params = f_band_params
        self.processing_dtype = processing_dtype

        # relative azimuth angle (in rad)
        if relative_azimuth_angle_radian is None:
            _phi = np.deg2rad(
                np.rad2deg(sun_azimuth_radian) - np.rad2deg(view_azimuth_radian)
            )
            self.relative_azimuth_angle_radian = np.where(
                _phi < 0, _phi + 2 * np.pi, _phi
            )

        else:
            self.relative_azimuth_angle_radian = relative_azimuth_angle_radian

    # Get delta
    def delta(self):
        return np.sqrt(
            np.power(np.tan(self.sun_zenith_radian), 2)
            + np.power(np.tan(self.view_zenith_radian), 2)
            - 2
            * np.tan(self.sun_zenith_radian)
            * np.tan(self.view_zenith_radian)
            * np.cos(self.relative_azimuth_angle_radian)
        )

    # Air Mass
    def masse(self):
        return 1 / np.cos(self.sun_zenith_radian) + 1 / np.cos(self.view_zenith_radian)

    # Get xsi
    def cos_xsi(self):
        return np.cos(self.sun_zenith_radian) * np.cos(
            self.view_zenith_radian
        ) + np.sin(self.sun_zenith_radian) * np.sin(self.view_zenith_radian) * np.cos(
            self.relative_azimuth_angle_radian
        )

    def sin_xsi(self):
        return np.sqrt(1 - np.power(self.cos_xsi(), 2))

    def xsi(self):
        xsi = np.arccos(self.cos_xsi())
        return xsi

    # Function t
    def cos_t(self):
        trig = (
            np.tan(self.sun_zenith_radian)
            * np.tan(self.view_zenith_radian)
            * np.sin(self.relative_azimuth_angle_radian)
        )
        # Coeficient for "t" any natural number is good, 1 or 2 are used
        coef = 1
        cos_t = (
            coef / self.masse() * np.sqrt(np.power(self.delta(), 2) + np.power(trig, 2))
        )
        return np.clip(cos_t, -1, 1)

    def sin_t(self):
        return np.sqrt(1 - np.power(self.cos_t(), 2))

    def t(self):
        return np.arccos(self.cos_t())

    def sec(self, x: np.ndarray) -> np.ndarray:
        return 1 / np.cos(x)

    # Function FV Ross_Thick, V is for volume scattering (Kernel)
    def f_vol(self):
        return (self.masse() / np.pi) * (
            (self.t() - self.sin_t() * self.cos_t() - np.pi)
            + (
                (1 + self.cos_xsi())
                / (2 * np.cos(self.sun_zenith_radian) * np.cos(self.view_zenith_radian))
            )
        )

    #  Function FR Li-Sparse, R is for roughness (surface roughness)
    def f_roughness(self):
        # HLS formula
        # https://userpages.umbc.edu/~martins/PHYS650/maignan%20brdf.pdf
        a = 1 / (np.cos(self.sun_zenith_radian) + np.cos(self.view_zenith_radian))
        return 4 / (3 * np.pi) * a * (
            (np.pi / 2 - self.xsi()) * self.cos_xsi() + self.sin_xsi()
        ) - (1 / 3)

    def calculate_array(self) -> np.ndarray:
        return (
            self.f_band_params.f_iso
            + self.f_band_params.f_geo * self.f_roughness()
            + self.f_band_params.f_vol * self.f_vol()
        )


class HLS(BRDFModelProtocol):
    """Directional model."""

    sun_zenith: np.ndarray
    sun_azimuth: np.ndarray
    view_zenith: np.ndarray
    view_azimuth: np.ndarray
    f_band_params: ModelParameters
    processing_dtype: DTypeLike = np.float32
    transform: Affine
    crs: CRSLike

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
        self.sun_zenith_angles_radian = get_sun_zenith_angles(s2_metadata)
        self.transform = s2_metadata.sun_angles.zenith.raster.transform
        self.crs = s2_metadata.crs

    def sensor_model(self) -> HLSBaseModel:
        return HLSBaseModel(
            sun_zenith_radian=np.deg2rad(self.sun_zenith),
            sun_azimuth_radian=np.deg2rad(self.sun_azimuth),
            view_zenith_radian=np.deg2rad(self.view_zenith),
            view_azimuth_radian=np.deg2rad(self.view_azimuth),
            f_band_params=self.f_band_params,
            processing_dtype=self.processing_dtype,
        )

    def sun_model(self) -> HLSBaseModel:
        # like sensor model, but:
        # sun_zenith_radian = calculated sun zenith angles
        # view_zenith_radian = np.zeros(self.sun_zenith_radian.shape)
        # phi = np.zeros(self.sun_zenith_radian.shape)
        return HLSBaseModel(
            sun_zenith_radian=self.sun_zenith_angles_radian,
            sun_azimuth_radian=np.deg2rad(self.sun_azimuth),
            view_zenith_radian=np.zeros(self.sun_zenith_angles_radian.shape),
            view_azimuth_radian=np.deg2rad(self.view_azimuth),
            relative_azimuth_angle_radian=np.zeros(self.sun_zenith_angles_radian.shape),
            f_band_params=self.f_band_params,
            processing_dtype=self.processing_dtype,
        )

    def calculate(self) -> ReferencedRaster:
        return ReferencedRaster.from_array_like(
            array_like=(
                self.sun_model().calculate_array()
                / self.sensor_model().calculate_array()
            ),
            transform=self.transform,
            crs=self.crs,
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
