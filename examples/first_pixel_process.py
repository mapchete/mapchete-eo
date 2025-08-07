import logging
import numpy.ma as ma
from rasterio.enums import Resampling
from typing import List, Optional, Union

from mapchete import Timer

from mapchete_eo.platforms.sentinel2.config import MaskConfig
from mapchete_eo.platforms.sentinel2.driver import Sentinel2Cube
from mapchete_eo.sort import TargetDateSort
from mapchete_eo.types import DateTimeLike, MergeMethod


logger = logging.getLogger(__name__)


def execute(
    element84_sentinel2: Sentinel2Cube,
    assets: List[str],
    target_height: int = 1,
    resampling: str = "bilinear",
    nodata: float = 0.0,
    merge_products_by: str = "s2:datastrip_id",
    mask_config: Union[MaskConfig, dict] = MaskConfig(scl_classes= ["nodata", "saturated_or_defected", "cloud_shadows", "thin_cirrus", "cloud_medium_probability", "cloud_high_probability"]),
    target_date: Optional[DateTimeLike] = None,
) -> ma.MaskedArray:
    '''
    This mapchete execute process reads the time-series and tries to fill an array with singular data value from the time-series.

    '''    
    logger.debug("Reading Sentinel-2 data stack.")
    with Timer() as t:
        data_stack = element84_sentinel2.read_levelled_np_array(
            target_height=target_height,
            assets=assets,
            resampling=Resampling[resampling],
            nodatavals=nodata,
            merge_products_by=merge_products_by,
            merge_method=MergeMethod.average,
            raise_empty=True,
            mask_config=MaskConfig.parse(mask_config),
            sort=TargetDateSort(target_date=target_date),
        )
    logger.debug("Sentinel-2 stack of shape %s read took %s", data_stack.shape, t)
    
    return data_stack[0]