from __future__ import annotations
from typing import Optional, Protocol

import numpy as np
from numpy.typing import DTypeLike

from mapchete_eo.platforms.sentinel2.metadata_parser import S2Metadata
from mapchete_eo.platforms.sentinel2.types import L2ABand


class BRDFModelProtocol(Protocol):
    """Defines base interface to all kind of models.

    Can be sensor models, sun models or directional models!
    """

    def calculate(self) -> np.ndarray: ...

    @staticmethod
    def from_s2metadata(
        s2_metadata: S2Metadata,
        band: L2ABand,
        detector_id: Optional[int] = None,
        processing_dtype: DTypeLike = np.float32,
    ) -> BRDFModelProtocol: ...
