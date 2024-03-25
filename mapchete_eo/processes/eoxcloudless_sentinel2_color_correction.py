import logging
from typing import Optional, Union

import numpy as np
import numpy.ma as ma
from mapchete.errors import MapcheteNodataTile
from shapely import unary_union
from shapely.geometry import shape

from mapchete_eo import image_operations
from mapchete_eo.array.buffer import buffer_array
from mapchete_eo.image_operations import compositing, filters
from mapchete_eo.processes.config import RGBCompositeConfig
from mapchete_eo.types import NodataVal

logger = logging.getLogger(__name__)


def execute(
    mp,
    bands: list = [1, 2, 3, 4],
    resampling: str = "nearest",
    matching_method: Optional[str] = "gdal",
    matching_max_zoom: int = 13,
    matching_precision: int = 8,
    fallback_to_higher_zoom: bool = False,
    out_dtype: Optional[str] = "uint8",
    out_nodata: NodataVal = None,
    fillnodata: bool = False,
    fillnodata_method: Union[
        image_operations.FillSelectionMethod, str
    ] = image_operations.FillSelectionMethod.nodata_neighbors,
    fillnodata_max_patch_size: int = 1,
    fillnodata_max_nodata_neighbors: int = 0,
    fillnodata_max_search_distance: int = 10,
    fillnodata_smoothing_iterations: int = 0,
    rgb_composite: Union[RGBCompositeConfig, dict] = RGBCompositeConfig(),
    desert_color_correction_flag: bool = False,
    desert_rgb_composite: Union[RGBCompositeConfig, dict] = RGBCompositeConfig(),
) -> ma.MaskedArray:
    """
    Extract color-corrected image from Sentinel-2 mosaic.

    Inputs:
    -------
    mosaic
        3 or 4 band 12bit data
    desert_mask
        AOI for different color correction over deserts

    Parameters
    ----------
    bands : list
        List of band indexes pointing to bands in the order [red, green, blue, nir].
    resampling : str (default: 'nearest')
        resampling used when reading from mosaic.
    matching_method : str ('gdal' or 'min') (default: 'gdal')
        gdal: Uses GDAL's standard method. Here, the target resolution is
            calculated by averaging the extent's pixel sizes over both x and y
            axes. This approach returns a zoom level which may not have the
            best quality but will speed up reading significantly.
        min: Returns the zoom level which matches the minimum resolution of the
            extents four corner pixels. This approach returns the zoom level
            with the best possible quality but with low performance. If the
            tile extent is outside of the destination pyramid, a
            TopologicalError will be raised.
    matching_max_zoom : int (optional, default: None)
        If set, it will prevent reading from zoom levels above the maximum.
    matching_precision : int (default: 8)
        Round resolutions to n digits before comparing.
    fallback_to_higher_zoom : bool (default: False)
        In case no data is found at zoom level, try to read data from higher
        zoom levels. Enabling this setting can lead to many IO requests in
        areas with no data.
    fillnodata : bool
        Interpolate nodata patches using GDAL. (default: false)
    fillnodata_method : str
        Method how to select areas to interpolate. (default: patch_size)
            - all: interpolate all nodata areas
            - patch_size: only interpolate areas up to a certain size. (defined by
                max_patch_size)
            - nodata_neighbors: only interpolate single nodata pixel.
    fillnodata_max_patch_size : int
        Minimum patch size in pixels to be interpolated. (default: 1)
    fillnodata_max_nodata_neighbors : int
        Maximum number of nodata neighbor pixels in "nodata_neighbors" method.
    fillnodata_max_search_distance : float
        The maxmimum number of pixels to search in all directions to find values to
        interpolate from.
    fillnodata_smoothing_iterations : int
        The number of 3x3 smoothing filter passes to run.
    rgb_composite: dict, RGBCompositeConfig
        default and possible values:
            red: Tuple[int, int] = (0, 2300)
            green: Tuple[int, int] = (0, 2300)
            blue: Tuple[int, int] = (0, 2300)
            gamma: float = 1.15
            saturation: float = 1.3
            clahe_clip_limit: float = 3.2
            fuzzy_radius: Optional[int] = 0
            sharpen: Optional[bool] = False
            smooth_water: Optional[bool] = False
            smooth_water_ndwi_threshold: float = 0.2
    desert_color_correction_flag: bool
        Use different color correction in desert areas. (default: False)
    desert_rgb_composite: dict, RGBCompositeConfig
        default and possible values are same as rgb_composite,
        to trigger define these values
    Output
    ------
    ma.MaskedArray
        8bit RGB
    """
    fillnodata_method = (
        image_operations.FillSelectionMethod[fillnodata_method]
        if isinstance(fillnodata_method, str)
        else fillnodata_method
    )
    rgb_composite = (
        RGBCompositeConfig(**rgb_composite)
        if isinstance(rgb_composite, dict)
        else rgb_composite
    )
    desert_rgb_composite = (
        RGBCompositeConfig(**desert_rgb_composite)
        if isinstance(desert_rgb_composite, dict)
        else desert_rgb_composite
    )

    logger.debug("read input mosaic")
    with mp.open("mosaic") as mosaic_inp:
        if mosaic_inp.is_empty():  # pragma: no cover
            logger.debug("mosaic empty")
            raise MapcheteNodataTile
        mosaic = mosaic_inp.read(
            indexes=bands,
            resampling=resampling,
            matching_method=matching_method,
            matching_max_zoom=matching_max_zoom,
            matching_precision=matching_precision,
            fallback_to_higher_zoom=fallback_to_higher_zoom,
            src_nodata=0,
            nodata=0,
        ).astype(np.int16, copy=False)
        nodata_mask = mosaic[0].mask
        if nodata_mask.all():  # pragma: no cover
            logger.debug("mosaic empty: all masked")
            raise MapcheteNodataTile

    # interpolate tiny nodata gaps
    if fillnodata:
        mosaic = image_operations.fillnodata(
            mosaic,
            method=fillnodata_method,
            max_patch_size=fillnodata_max_patch_size,
            max_nodata_neighbors=fillnodata_max_nodata_neighbors,
            max_search_distance=fillnodata_max_search_distance,
            smoothing_iterations=fillnodata_smoothing_iterations,
        )
        nodata_mask = mosaic.mask[0].copy()

    # get water masks
    if rgb_composite.smooth_water:
        water_mask = _water_mask(
            mosaic, ndwi_threshold=rgb_composite.smooth_water_ndwi_threshold
        )
        logger.debug(
            "Input mosaic tile is "
            f"{_percent_masked(water_mask, nodata_mask)} % water"
        )

    # apply color correction
    corrected = image_operations.color_correct(
        rgb=image_operations.linear_normalization(
            bands=mosaic[:3],
            bands_minmax_values=(
                rgb_composite.red,
                rgb_composite.green,
                rgb_composite.blue,
            ),
            out_dtype=str(out_dtype),
        ),
        gamma=rgb_composite.gamma,
        clahe_flag=rgb_composite.clahe_flag,
        clahe_clip_limit=rgb_composite.clahe_clip_limit,
        clahe_tile_grid_size=rgb_composite.clahe_tile_grid_size,
        sigmoidal_flag=rgb_composite.sigmoidal_flag,
        sigmoidal_constrast=rgb_composite.sigmoidal_contrast,
        sigmoidal_bias=rgb_composite.sigmoidal_bias,
        saturation=rgb_composite.saturation,
        calculations_dtype=rgb_composite.calculations_dtype,
    )

    # apply special color correction to desert areas and merge with corrected
    if desert_color_correction_flag:
        if "desert_mask" in mp.params["input"]:
            desert_mask = unary_union(
                [shape(f["geometry"]) for f in mp.open("desert_mask").read()]
            )
        else:  # pragma: no cover
            raise ValueError(
                "a vector input with the key 'desert_mask' has to be provided"
            )

        if not desert_mask.is_empty:
            # clip original mosaic with desert mask
            desert_mosaic = mp.clip(
                mosaic, [dict(geometry=desert_mask)], inverted=False
            ).astype("uint16")[:3]
            logger.debug("apply other color correction for desert areas")
            # apply custom scaling to 8bit
            # apply custom color correction
            # merge with existing corrected pixels
            corrected = compositing.normal(
                image_operations.color_correct(
                    rgb=image_operations.linear_normalization(
                        bands=desert_mosaic,
                        bands_minmax_values=(
                            desert_rgb_composite.red,
                            desert_rgb_composite.green,
                            desert_rgb_composite.blue,
                        ),
                        out_dtype=str(out_dtype),
                    ),
                    gamma=desert_rgb_composite.gamma,
                    clahe_flag=desert_rgb_composite.clahe_flag,
                    clahe_clip_limit=desert_rgb_composite.clahe_clip_limit,
                    clahe_tile_grid_size=desert_rgb_composite.clahe_tile_grid_size,
                    sigmoidal_flag=desert_rgb_composite.sigmoidal_flag,
                    sigmoidal_constrast=desert_rgb_composite.sigmoidal_contrast,
                    sigmoidal_bias=desert_rgb_composite.sigmoidal_bias,
                    saturation=desert_rgb_composite.saturation,
                    calculations_dtype=desert_rgb_composite.calculations_dtype,
                ),
                compositing.fuzzy_alpha_mask(
                    corrected,
                    mask=desert_mosaic.mask,
                    radius=desert_rgb_composite.fuzzy_radius,
                ),
            )[:3]

    # Post Color Correction operations on RGB composites

    # smooth out water areas
    if rgb_composite.smooth_water and water_mask.any():
        logger.debug("smooth water areas")
        corrected = ma.where(
            water_mask,
            filters.gaussian_blur(corrected, radius=6),
            corrected,
        )
        corrected = ma.where(
            buffer_array(water_mask, buffer=2),
            filters.smooth_more(corrected),
            corrected,
        )

    # sharpen non-water areas
    if rgb_composite.sharpen:
        if rgb_composite.smooth_water and not water_mask.all():
            logger.debug("sharpen output")
            corrected = ma.where(water_mask, corrected, filters.sharpen(corrected))
        else:
            corrected = filters.sharpen(corrected)

    return ma.masked_where(corrected == out_nodata, corrected, copy=False)


def _percent_masked(
    mask: np.ndarray,
    nodata_mask: np.ndarray,
    round_by: int = 2,
) -> float:
    # divide number of masked and valid pixels by number of valid pixels
    return round(
        100
        * np.where(nodata_mask, False, mask).sum()
        / (nodata_mask.size - nodata_mask.sum()),
        round_by,
    )


def _water_mask(
    bands_array: ma.MaskedArray, ndwi_threshold: float = 0.2
) -> ma.MaskedArray:
    if len(bands_array) != 4:  # pragma: no cover
        raise ValueError("smooth_water only works with RGBNir bands")

    red, green, blue, nir = bands_array.astype(np.float16, copy=False)
    return ma.MaskedArray(
        data=np.where(
            ((green - nir) / (green + nir) > ndwi_threshold)
            & ((blue + green) / 2 > red),
            True,
            False,
        ),
        mask=bands_array[0].mask,
    )
