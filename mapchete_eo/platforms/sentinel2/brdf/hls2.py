# """
# New implementation from November 2024
# """
from __future__ import annotations

from typing import Optional
import numpy as np
import numpy.ma as ma
from numpy.typing import DTypeLike

from mapchete_eo.platforms.sentinel2.brdf.config import ModelParameters
from mapchete_eo.platforms.sentinel2.brdf.protocols import BRDFModelProtocol
from mapchete_eo.platforms.sentinel2.metadata_parser import S2Metadata
from mapchete_eo.platforms.sentinel2.types import L2ABand


class HLS2(BRDFModelProtocol):
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
        # TODO: initialize model with whichever S2 metadata required
        # NOTE: try to read / get / resample all data here
        # NOTE: look at mapchete_eo.platforms.sentinel2.brdf.hls module for hints
        raise NotImplementedError()

    def calculate(self) -> ma.MaskedArray:
        # TODO: calculate model array
        # NOTE: this was renamed from get_band_params() and will be needed to get the correction
        raise NotImplementedError()

    @staticmethod
    def from_s2metadata(
        s2_metadata: S2Metadata,
        band: L2ABand,
        detector_id: Optional[int] = None,
        processing_dtype: DTypeLike = np.float32,
    ) -> HLS2:
        return HLS2(
            s2_metadata=s2_metadata,
            band=band,
            detector_id=detector_id,
            processing_dtype=processing_dtype,
        )
