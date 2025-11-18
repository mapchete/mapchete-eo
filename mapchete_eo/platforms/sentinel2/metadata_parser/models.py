from __future__ import annotations

import logging
import warnings
from typing import Dict

import numpy as np
import numpy.ma as ma
from pydantic import BaseModel
from mapchete.io.raster import ReferencedRaster
from rasterio.fill import fillnodata

from mapchete_eo.exceptions import CorruptedProductMetadata
from mapchete_eo.platforms.sentinel2.types import (
    SunAngle,
    ViewAngle,
)

logger = logging.getLogger(__name__)


class SunAngleData(BaseModel):
    model_config = dict(arbitrary_types_allowed=True)
    raster: ReferencedRaster
    mean: float


class SunAnglesData(BaseModel):
    azimuth: SunAngleData
    zenith: SunAngleData

    def get_angle(self, angle: SunAngle) -> SunAngleData:
        if angle == SunAngle.azimuth:
            return self.azimuth
        elif angle == SunAngle.zenith:
            return self.zenith
        else:
            raise KeyError(f"unknown angle: {angle}")


class ViewingIncidenceAngle(BaseModel):
    model_config = dict(arbitrary_types_allowed=True)
    detectors: Dict[int, ReferencedRaster]
    mean: float

    def merge_detectors(
        self, fill_edges: bool = True, smoothing_iterations: int = 3
    ) -> ReferencedRaster:
        if not self.detectors:
            raise CorruptedProductMetadata("no viewing incidence angles available")
        sample = next(iter(self.detectors.values()))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            merged = np.nanmean(
                np.stack([raster.data for raster in self.detectors.values()]), axis=0
            )
        if fill_edges:
            merged = fillnodata(
                ma.masked_invalid(merged), smoothing_iterations=smoothing_iterations
            )
        return ReferencedRaster.from_array_like(
            array_like=ma.masked_invalid(merged),
            transform=sample.transform,
            crs=sample.crs,
        )


class ViewingIncidenceAngles(BaseModel):
    azimuth: ViewingIncidenceAngle
    zenith: ViewingIncidenceAngle

    def get_angle(self, angle: ViewAngle) -> ViewingIncidenceAngle:
        if angle == ViewAngle.azimuth:
            return self.azimuth
        elif angle == ViewAngle.zenith:
            return self.zenith
        else:
            raise KeyError(f"unknown angle: {angle}")
