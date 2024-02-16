import logging
from typing import Union

import numpy as np
import numpy.ma as ma
from shapely import unary_union
from shapely.geometry import Polygon, shape

from mapchete_eo import image_operations
from mapchete_eo.array.color import color_array
from mapchete_eo.image_operations import compositing

logger = logging.getLogger(__name__)


def execute(
    mp,
    matching_method: str = "min",
    matching_max_zoom: int = 13,
    matching_precision: int = 8,
    fallback_to_higher_zoom: bool = False,
    ocean_color: str = "#182c4e",
    land_color: str = "#ffffff",
    ocean_depth_opacity: float = 0.8,
    bathymetry_opacity: float = 0.8,
    resampling: Union[str, None] = "bilinear",
    fillnodata: bool = False,
    fillnodata_method: Union[
        image_operations.FillSelectionMethod, str
    ] = image_operations.FillSelectionMethod.nodata_neighbors,
    fillnodata_max_patch_size: int = 3,
    fillnodata_max_nodata_neighbors: int = 9,
    fillnodata_max_search_distance: float = 0.5,
    fillnodata_smoothing_iterations: int = 3,
):
    fillnodata_method = (
        image_operations.FillSelectionMethod[fillnodata_method]
        if isinstance(fillnodata_method, str)
        else fillnodata_method
    )

    # read bad aois mask
    if "mosaic_mask" in mp.params["input"]:
        mask_geom = unary_union(
            [shape(f["geometry"]) for f in mp.open("mosaic_mask").read()]
        )
    else:
        mask_geom = Polygon()

    # just return empty array, when mask covers tile completely
    if mask_geom.equals(mp.tile.bbox):
        out_shape = (3, *mp.tile.shape)
        out = ma.masked_array(
            data=np.zeros(out_shape, dtype=np.uint8),
            mask=np.ones(out_shape, dtype=bool),
        ).astype(np.uint8, copy=False)
    else:
        with mp.open("mosaic") as src:
            out = src.read(
                resampling=resampling,
                matching_method=matching_method,
                matching_max_zoom=matching_max_zoom,
                matching_precision=matching_precision,
                fallback_to_higher_zoom=fallback_to_higher_zoom,
            )
            if fillnodata:
                out = ma.clip(out, 1, 255).astype(np.uint8, copy=False)
    if not mask_geom.is_empty or not mask_geom.equals(mp.tile.bbox):
        out = mp.clip(out, [{"geometry": mask_geom}], inverted=True).astype(
            np.uint8, copy=False
        )

    # interpolate tiny nodata gaps
    if fillnodata:
        out = image_operations.fillnodata(
            out,
            method=fillnodata_method,
            max_patch_size=fillnodata_max_patch_size,
            max_nodata_neighbors=fillnodata_max_nodata_neighbors,
            max_search_distance=fillnodata_max_search_distance,
            smoothing_iterations=fillnodata_smoothing_iterations,
        ).astype(np.uint8, copy=False)

    if "land_mask" in mp.input:
        with mp.open("land_mask") as src:
            out = compositing.normal(
                mp.clip(
                    color_array(mp.tile.shape, land_color), src.read(), inverted=False
                ),
                out,
            )

    if "fuzzy_ocean_mask" in mp.input:
        with mp.open("fuzzy_ocean_mask") as src:
            out = compositing.normal(
                out,
                src.read(),
            )

    if "ocean_depth" in mp.input:
        with mp.open("ocean_depth") as src:
            out = compositing.multiply(out, src.read(), opacity=ocean_depth_opacity)

    if "bathymetry" in mp.input:
        with mp.open("bathymetry") as src:
            out = compositing.multiply(out, src.read(), opacity=bathymetry_opacity)

    if out.mask.all():
        return "empty"

    # fix accidental 0 values and avoid them getting nodata
    out[~out.mask] = out.clip(1, None)[~out.mask]

    if out.mask.any():
        blue = color_array(mp.tile.shape, ocean_color)
        out = compositing.normal(blue, out)

    return out[:3]
