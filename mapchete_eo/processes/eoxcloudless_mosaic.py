import logging
from typing import Union

import numpy as np
import numpy.ma as ma
from mapchete import Timer
from mapchete.errors import MapcheteNodataTile
from orgonite import cloudless
from rasterio.enums import Resampling

from mapchete_eo.exceptions import EmptyStackException
from mapchete_eo.platforms.sentinel2.config import BRDFConfig, BRDFModels, MaskConfig
from mapchete_eo.platforms.sentinel2.types import Resolution
from mapchete_eo.types import MergeMethod

logger = logging.getLogger(__name__)


def execute(
    mp,
    target_height: int = 6,
    assets: list = ["red", "green", "blue", "nir"],
    resampling: str = "bilinear",
    nodata: Union[float, int, None] = 0.0,
    merge_products_by: str = "s2:datastrip_id",
    add_indexes: bool = False,
    mask_config: MaskConfig = MaskConfig(cloud_probability_threshold=70),
    method: str = "brightness",
    from_brightness_extract_method: str = "median",
    from_brightness_average_over: int = 3,
    considered_bands: int = 3,
) -> ma.MaskedArray:
    if method not in [
        "water_mosaic",
        "brightness",
        "ndvi_linreg",
        "weighted_avg",
        "max_ndvi",
    ]:
        raise ValueError("invalid extraction method given")
    if add_indexes and method not in ["brightness", "max_ndvi"]:
        raise ValueError(
            "add_indexes option only works with 'brigtness' or "
            "'max_ndvi' extraction methods"
        )

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
        logger.debug("Reading Sentinel-2 data stack.")
        with Timer() as t:
            try:
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
                )
            except EmptyStackException:
                raise MapcheteNodataTile
        logger.debug(
            "Sentinel-2 stack of shape %s read with BRDF took %s", s2_arr.shape, t
        )

    return ma.MaskedArray(
        _extract_mosaic(
            stack_data=s2_arr,
            method=method,
            from_brightness_extract_method=from_brightness_extract_method,
            average_over=from_brightness_average_over,
            considered_bands=considered_bands,
        ).astype(np.uint16)
    )


def _extract_mosaic(
    stack_data: ma.MaskedArray,
    method: str,
    min_ndvi: float = 0.1,
    max_ndvi: float = 0.95,
    average_over: int = 0,
    considered_bands: int = 3,
    simulation_value: float = 0.4,
    value_range_weight: float = 1.5,
    core_value_range_weight: float = 8.5,
    value_range_min: int = 25,
    value_range_max: int = 3000,
    core_value_range_min: int = 50,
    core_value_range_max: int = 1000,
    input_values_threshold_multiplier: float = 2.1,
    from_brightness_extract_method="third_quartile",
    keep_slice_indexes: bool = False,
) -> ma.MaskedArray:
    # extract mosaic
    logger.debug("run orgonite '%s' method", method)
    with Timer() as t:
        if method == "brightness":
            mosaic = cloudless.from_brightness(
                stack_data,
                average_over=average_over,
                considered_bands=considered_bands,
                keep_slice_indexes=keep_slice_indexes,
            )
        elif method == "ndvi_linreg":
            mosaic = cloudless.ndvi_linreg(
                stack_data,
                simulation_value=simulation_value,
                value_range_weight=value_range_weight,
                core_value_range_weight=core_value_range_weight,
                value_range_min=value_range_min,
                value_range_max=value_range_max,
                core_value_range_min=core_value_range_min,
                core_value_range_max=core_value_range_max,
            )
        elif method == "weighted_avg":
            mosaic = cloudless.weighted_avg(
                stack_data,
                value_range_min=value_range_min,
                value_range_max=value_range_max,
                value_range_weight=value_range_weight,
                core_value_range_min=core_value_range_min,
                core_value_range_max=core_value_range_max,
                core_value_range_weight=core_value_range_weight,
                input_values_threshold_multiplier=input_values_threshold_multiplier,
            )
        elif method == "max_ndvi":
            mosaic = cloudless.max_ndvi(
                stack_data,
                min_ndvi=min_ndvi,
                max_ndvi=max_ndvi,
                from_brightness_extract_method=from_brightness_extract_method,
                from_brightness_average_over=average_over,
                keep_slice_indexes=keep_slice_indexes,
            )
        elif method == "water_mosaic":
            average = False
            if average_over > 1:
                average = True
            mosaic = cloudless.l2a_water(
                stack=stack_data,
                average=average,
                min_ndwi=min_ndvi,
                max_ndwi=max_ndvi,
                from_brightness_extract_method=from_brightness_extract_method,
                from_brightness_average_over=average_over,
                keep_slice_indexes=keep_slice_indexes,
            )
        else:
            raise KeyError("no method '%s' available in orgonite" % method)
    logger.debug("extracted in %s", t)
    return mosaic
