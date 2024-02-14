import logging
from typing import Union

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

    with mp.open("mosaic") as src:
        out = src.read(
            resampling=resampling,
            matching_method=matching_method,
            matching_max_zoom=matching_max_zoom,
            matching_precision=matching_precision,
            fallback_to_higher_zoom=fallback_to_higher_zoom,
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
        )

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
