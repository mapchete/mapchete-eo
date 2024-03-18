import logging
from typing import Generator, Optional, Tuple, Union

import numpy.ma as ma
from mapchete import Timer
from mapchete.errors import MapcheteNodataTile
from mapchete.processing.mp import MapcheteProcess

from mapchete_eo.base import InputTile
from mapchete_eo.platforms.sentinel2.config import MaskConfig
from mapchete_eo.processes.eoxcloudless_mosaic import create_mosaic
from mapchete_eo.processes.merge_rasters import MergeMethod, merge_rasters
from mapchete_eo.types import DateTimeLike

logger = logging.getLogger(__name__)


def execute(
    mp: MapcheteProcess,
    target_height: int = 6,
    merge_method: MergeMethod = MergeMethod.footprint_gradient,
    gradient_buffer: int = 10,
    region_group_name: str = "sentinel2",
    assets: list = ["red", "green", "blue", "nir"],
    # default mosaic settings
    resampling: str = "bilinear",
    nodata: Union[float, int, None] = 0.0,
    merge_products_by: str = "s2:datastrip_id",
    read_masks: bool = False,
    mask_config: Union[MaskConfig, dict] = MaskConfig(cloud_probability_threshold=70),
    custom_mask_config: Union[None, MaskConfig, dict] = None,
    from_brightness_extract_method: str = "median",
    from_brightness_average_over: int = 3,
    considered_bands: int = 3,
    target_date: Optional[DateTimeLike] = None,
    # specific settings for each region
    region_specific_mosaic_settings: Optional[dict] = None,
) -> ma.MaskedArray:
    """
    Extract mosaics for each EO cube in group and merge them in the end.
    """
    # per default, these settings are used for all mosaics
    default_mosaic_settings = dict(
        target_height=target_height,
        resampling=resampling,
        nodata=nodata,
        merge_products_by=merge_products_by,
        read_masks=read_masks,
        mask_config=mask_config,
        custom_mask_config=custom_mask_config,
        from_brightness_extract_method=from_brightness_extract_method,
        from_brightness_average_over=from_brightness_average_over,
        considered_bands=considered_bands,
        target_date=target_date,
    )

    # here, each region can have its own settings
    region_specific_mosaic_settings = region_specific_mosaic_settings or {}

    mosaics = []
    region_footprints = []
    with Timer() as tt:
        for region_name, region in eo_region_cubes(mp, region_group_name):
            mosaic = create_mosaic(
                region,
                assets=assets,
                **dict(
                    default_mosaic_settings,
                    **region_specific_mosaic_settings.get(region_name, {})
                )
            )
            if mosaic.mask.all():
                logger.debug("%s mosaic is empty", region_name)
                continue

            mosaics.append(mosaic)
            region_footprints.append(region.area)

    logger.debug("%s mosaics created in %s", len(mosaics), tt)

    if len(mosaics) == 0:
        raise MapcheteNodataTile("no input mosaics found")

    with Timer() as tt:
        merged = merge_rasters(
            mosaics,
            mp.tile,
            footprints=region_footprints,
            method=merge_method,
            gradient_buffer=gradient_buffer,
        )
    logger.debug("%s mosaics merged in %s", len(mosaics), tt)
    return merged


# just for typing
def eo_region_cubes(
    mp: MapcheteProcess, group_name: str = "sentinel2"
) -> Generator[Tuple[str, InputTile], None, None]:
    for name, cube in mp.open(group_name):
        if cube.is_empty():
            logger.debug("%s is emtpy", name)
        else:
            yield (name, cube)
