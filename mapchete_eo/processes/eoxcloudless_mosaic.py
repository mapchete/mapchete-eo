import logging
from typing import Optional, Union

import numpy as np
import numpy.ma as ma
from mapchete import Timer
from mapchete.errors import MapcheteNodataTile
from orgonite import cloudless
from rasterio.enums import Resampling

from mapchete_eo.platforms.sentinel2.config import (
    BRDFConfig,
    BRDFModels,
    MaskConfig,
    parse_mask_config,
)
from mapchete_eo.platforms.sentinel2.types import Resolution
from mapchete_eo.sort import TargetDateSort
from mapchete_eo.types import DateTimeLike, MergeMethod

logger = logging.getLogger(__name__)


def execute(
    mp,
    target_height: int = 6,
    assets: list = ["red", "green", "blue", "nir"],
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
) -> ma.MaskedArray:
    mask_config = parse_mask_config(mask_config)
    if custom_mask_config is not None:
        custom_mask_config = parse_mask_config(custom_mask_config)

    # clip geometry
    if "clip" in mp.params["input"]:
        clip_geom = mp.open("clip").read()
        if not clip_geom:
            logger.debug("no clip data over tile")
            raise MapcheteNodataTile("no clip data over tile")
    else:
        clip_geom = []

    # Read all the data first and ideally just once
    # Masks reading should've been done while reading
    with mp.open("sentinel2") as mp_src:
        # Read Masks separately with different mask_config
        # for other/later use
        if read_masks:
            if custom_mask_config is None:
                custom_mask_config = mask_config
            logger.debug("Reading Sentinel-2 custom masks stack.")
            with Timer() as t:
                s2_custom_mask = mp_src.read_masks(
                    mask_config=custom_mask_config,
                    sort=TargetDateSort(target_date=target_date),
                )
            logger.debug(
                f"Sentinel-2 custom masks stack {s2_custom_mask.shape}. read in {t}"
            )

        logger.debug("Reading Sentinel-2 data stack.")
        with Timer() as t:
            s2_arr = mp_src.read_levelled_np_array(
                target_height=target_height,
                assets=assets,
                resampling=Resampling[resampling],
                nodatavals=nodata,
                merge_products_by=merge_products_by,
                merge_method=MergeMethod.average,
                raise_empty=True,
                brdf_config=BRDFConfig(
                    bands=assets, model=BRDFModels.HLS, resolution=Resolution["60m"]
                ),
                mask_config=mask_config,
                sort=TargetDateSort(target_date=target_date),
            )
        logger.debug(
            "Sentinel-2 stack of shape %s read with BRDF took %s", s2_arr.shape, t
        )

    return ma.MaskedArray(
        _extract_brightness_mosaic(
            stack_data=s2_arr,
            from_brightness_extract_method=from_brightness_extract_method,
            average_over=from_brightness_average_over,
            considered_bands=considered_bands,
            keep_slice_indexes=False,
        ).astype(np.uint16)
    )


def _extract_brightness_mosaic(
    stack_data: ma.MaskedArray,
    average_over: int = 0,
    considered_bands: int = 3,
    from_brightness_extract_method: str = "median",
    keep_slice_indexes: bool = False,
) -> ma.MaskedArray:
    # extract mosaic
    logger.debug(
        "Run orgonite brightness mosaic with "
        f"{from_brightness_extract_method} method"
    )
    with Timer() as t:
        mosaic = cloudless.from_brightness(
            stack_data,
            average_over=average_over,
            considered_bands=considered_bands,
            extract_method=from_brightness_extract_method,
            keep_slice_indexes=keep_slice_indexes,
        )
    logger.debug(f"Orgonite mosaic extracted in {t}")
    return mosaic
