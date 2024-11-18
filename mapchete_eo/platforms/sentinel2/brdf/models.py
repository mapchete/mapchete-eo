from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from numpy.typing import DTypeLike

from mapchete_eo.platforms.sentinel2.brdf.protocols import BRDFModelProtocol
from mapchete_eo.platforms.sentinel2.brdf.config import BRDFModels
from mapchete_eo.platforms.sentinel2.brdf.hls import HLS
from mapchete_eo.platforms.sentinel2.brdf.ross_thick import RossThick

# from mapchete_eo.platforms.sentinel2.brdf.hls2 import HLS2
from mapchete_eo.platforms.sentinel2.metadata_parser import S2Metadata
from mapchete_eo.platforms.sentinel2.types import L2ABand

logger = logging.getLogger(__name__)


def get_model(
    model: BRDFModels,
    s2_metadata: S2Metadata,
    band: L2ABand,
    detector_id: Optional[int] = None,
    processing_dtype: DTypeLike = np.float32,
) -> BRDFModelProtocol:
    match model:
        case BRDFModels.HLS:
            return HLS.from_s2metadata(
                s2_metadata=s2_metadata,
                band=band,
                detector_id=detector_id,
                processing_dtype=processing_dtype,
            )
        case BRDFModels.RossThick:
            return RossThick.from_s2metadata(
                s2_metadata=s2_metadata,
                band=band,
                detector_id=detector_id,
                processing_dtype=processing_dtype,
            )
        case _:
            raise KeyError(f"unkown or not implemented model: {model}")
