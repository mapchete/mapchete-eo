from __future__ import annotations

import numpy as np
from numpy.typing import DTypeLike

from typing import Optional

from affine import Affine
from mapchete.io.raster import ReferencedRaster
from mapchete.types import CRSLike

from mapchete_eo.platforms.sentinel2.brdf.protocols import (
    BRDFModelProtocol,
)
from mapchete_eo.platforms.sentinel2.brdf.config import L2ABandFParams, ModelParameters
from mapchete_eo.platforms.sentinel2.brdf.hls import _get_viewing_angles
from mapchete_eo.platforms.sentinel2.metadata_parser import S2Metadata
from mapchete_eo.platforms.sentinel2.types import L2ABand


class RossThick(BRDFModelProtocol):
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

        self.sun_zenith_radian = np.deg2rad(self.sun_zenith)
        self.sun_azimuth_radian = np.deg2rad(self.sun_azimuth)
        self.view_zenith_radian = np.deg2rad(self.view_zenith)
        self.view_azimuth_radian = np.deg2rad(self.view_azimuth)

        self.relative_azimuth_angle_radian = np.abs(
            self.view_azimuth_radian - self.sun_azimuth_radian
        )

        self.transform = s2_metadata.sun_angles.zenith.raster.transform
        self.crs = s2_metadata.crs

    def calculate(self) -> ReferencedRaster:
        """
        Ross-Thick BRDF model function that computes the C factor.

        Parameters:
        - f_iso, f_vol, f_geo: BRDF model parameters to fit.
        - sza: Solar Zenith Angle (in degrees).
        - vza: View Zenith Angle (in degrees).
        - raa: Relative Azimuth Angle (in degrees).
        - normalize: Normalize by nadir sensor with sun angles.

        Returns:
        - C factor according to the Ross-Thick BRDF model.
        """
        sza = self.sun_zenith_radian
        vza = self.view_zenith_radian
        raa = self.relative_azimuth_angle_radian

        f_iso = self.f_band_params.f_iso
        f_vol = self.f_band_params.f_vol
        f_geo = self.f_band_params.f_geo

        # Scale vza for fitting
        vza = vza / (np.pi / 2)

        def compute_kernels(vza, sza, raa):
            # Cosine of view and solar zenith angles
            cos_vza = np.cos(vza)
            cos_sza = np.cos(sza)

            # Phase angle (theta)
            cos_theta = cos_vza * cos_sza + np.sin(vza) * np.sin(sza) * np.cos(raa)
            theta = np.arccos(np.clip(cos_theta, -1.0, 1.0))

            # Ross-Thick Kernel (K_vol)
            K_vol = ((np.pi - theta) * cos_theta + np.sin(theta)) / (
                cos_vza + cos_sza
            ) - np.pi / 4

            # Li-Sparse Kernel (K_geo)
            tan_vza = np.tan(vza)
            tan_sza = np.tan(sza)
            D = np.sqrt(tan_vza**2 + tan_sza**2 - 2 * tan_vza * tan_sza * np.cos(raa))
            cos_phase = np.clip((2 * D / (D + tan_vza + tan_sza)), -1.0, 1.0)
            K_geo = (1 / np.pi) * (D - cos_phase * (tan_vza + tan_sza)) + np.arctan(D)

            return K_vol, K_geo

        # Calculate kernels for actual angles
        K_vol, K_geo = compute_kernels(vza, sza, raa)
        C_actual = f_iso + f_vol * K_vol + f_geo * K_geo

        # Calculate kernels for nadir (0° view, 0° relative azimuth)
        K_vol_nadir, K_geo_nadir = compute_kernels(0, sza, 0)
        C_nadir = f_iso + f_vol * K_vol_nadir + f_geo * K_geo_nadir

        # Normalize  and return c-factors
        return ReferencedRaster.from_array_like(
            array_like=(C_nadir / C_actual),
            transform=self.transform,
            crs=self.crs,
        )

    @staticmethod
    def from_s2metadata(
        s2_metadata: S2Metadata,
        band: L2ABand,
        detector_id: Optional[int] = None,
        processing_dtype: DTypeLike = np.float32,
    ) -> RossThick:
        return RossThick(
            s2_metadata=s2_metadata,
            band=band,
            detector_id=detector_id,
            processing_dtype=processing_dtype,
        )
