import logging
import numpy as np
import numpy.ma as ma
from rasterio.enums import Resampling

from mapchete_eo.platforms.sentinel2.driver import Sentinel2Cube


logger = logging.getLogger(__name__)


def execute(
    element84_sentinel2: Sentinel2Cube,
    resampling: str = "bilinear",
    nodata: float = 0.0,
) -> ma.MaskedArray:
    """
    Calculate NDVI (Normalized Difference Vegetation Index).
    """
    logger.debug("Reading Sentinel-2 NIR and Red bands.")
    
    # Read the first available cloud-free pixel for NIR and Red
    # (Simplified for example purposes)
    data = element84_sentinel2.read_np_array(
        assets=["red", "nir"],
        resampling=Resampling[resampling],
        nodatavals=nodata,
    )
    
    red = data[0].astype(float)
    nir = data[1].astype(float)
    
    # Calculate NDVI: (NIR - Red) / (NIR + Red)
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (nir - red) / (nir + red)
        ndvi[np.isnan(ndvi)] = nodata
        
    # NDVI is typically in range [-1, 1].
    # For visualization, we could scale it to 0-255 or just return the float array.
    # Here we return it as a single-band float32 array.
    return ma.masked_array(
        data=ndvi.astype(np.float32),
        mask=data.mask[0]
    )
