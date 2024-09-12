import logging
from typing import Optional

from mapchete import MapcheteProcess, RasterInput
import numpy as np
import numpy.ma as ma
from mapchete.errors import MapcheteNodataTile
from mapchete.types import NodataVal

from mapchete_eo.exceptions import EmptyStackException
from mapchete_eo.image_operations import dtype_scale

logger = logging.getLogger(__name__)


def execute(
    mp: MapcheteProcess,
    inp: RasterInput,
    bands: list = [1, 2, 3, 4],
    resampling: str = "nearest",
    matching_method: Optional[str] = "gdal",
    matching_max_zoom: int = 13,
    matching_precision: int = 8,
    fallback_to_higher_zoom: bool = False,
    out_dtype: Optional[str] = "uint8",
    out_nodata: NodataVal = None,
    max_source_value: float = 10000.0,
    max_output_value: Optional[float] = None,
) -> ma.MaskedArray:
    """
    Scale input to different value range.

    Inputs:
    -------
    inp
        raster input to be scaled

    Parameters:
    -----------
    bands : list
        List of band indexes.
    tresampling : str (default: 'nearest')
        Resampling used when reading from mosaic.
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
    out_dtype: string
        Output dtype for the target values, should fit the designated scaling from source,
        if the output scaled values do not fit, they will be clipped to the output dtype.
    out_nodata: float, int
        Output Nodata, per default read from output nodata of the mapchete config.
    max_source_value : float
        Upper limit for clipping and scaling (e.g. 10000 for Sentinel-2).
    max_output_value : float, None
        Output value range (e.g. 255 for 8 bit). If None it will be determined by the out_dtype

    Output:
    -------
    ma.ndarray
        stretched input bands
    """
    logger.debug("read input mosaic")
    if inp.is_empty():
        logger.debug("mosaic empty")
        raise MapcheteNodataTile
    try:
        mosaic = inp.read(
            indexes=bands,
            resampling=resampling,
            matching_method=matching_method,
            matching_max_zoom=matching_max_zoom,
            matching_precision=matching_precision,
            fallback_to_higher_zoom=fallback_to_higher_zoom,
        ).astype(np.int16, copy=False)
    except EmptyStackException:
        logger.debug("mosaic empty: EmptyStackException")
        raise MapcheteNodataTile
    if mosaic[0].mask.all():
        logger.debug("mosaic empty: all masked")
        raise MapcheteNodataTile

    if mp.output_params and mp.output_params.get("nodata") and out_nodata is None:
        out_nodata = mp.output_params.get("nodata")
    elif out_nodata is None:
        logger.debug("Out nodata is None setting it to 0")
        out_nodata = 0

    logger.debug(
        f"scale input raster values to wished dtype up to the max source value: {max_output_value}"
    )
    return dtype_scale(
        bands=mosaic,
        nodata=out_nodata,
        out_dtype=out_dtype,
        max_source_value=max_source_value,
        max_output_value=max_output_value,
    )
