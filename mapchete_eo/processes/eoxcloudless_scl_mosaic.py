import logging
from enum import Enum
from typing import Tuple

import numpy.ma as ma
from mapchete.errors import MapcheteNodataTile
from rasterio.enums import Resampling
from scipy.stats import mode

from mapchete_eo.platforms.sentinel2.config import MaskConfig, SceneClassification
from mapchete_eo.platforms.sentinel2.driver import InputTile

logger = logging.getLogger(__name__)


class SelectionMethod(str, Enum):
    majority = "majority"
    first_permanent = "first_permanent"


def execute(
    sentinel2: InputTile,
    scl_asset_name: str = "scl",
    selection_method: SelectionMethod = SelectionMethod.majority,
    permanent_classes: Tuple[SceneClassification, ...] = (
        SceneClassification.not_vegetated,
        SceneClassification.vegetation,
        SceneClassification.water,
    ),
) -> ma.MaskedArray:
    if sentinel2.is_empty():
        raise MapcheteNodataTile

    # read full stack and output the most occuring values
    if selection_method == SelectionMethod.majority:
        cube = sentinel2.read_np_array(
            assets=[scl_asset_name],
            resampling=Resampling.nearest,
            mask_config=MaskConfig(
                footprint=False,
                scl_classes=[
                    cls for cls in SceneClassification if cls not in permanent_classes
                ],
            ),
        )
        logger.debug("generate mode of SCL values...")
        mod_result, _ = mode(cube, axis=0)
        return mod_result

    # read available slices until area is fully covered with "permanent_classes"
    elif selection_method == SelectionMethod.first_permanent:
        return sentinel2.read_levelled_np_array(
            target_height=1,
            assets=[scl_asset_name],
            resampling=Resampling.nearest,
            mask_config=MaskConfig(
                footprint=False,
                scl_classes=[
                    cls for cls in SceneClassification if cls not in permanent_classes
                ],
            ),
        )[0]

    else:  # pragma: no cover
        raise KeyError(f"invalid method given: {selection_method}")
