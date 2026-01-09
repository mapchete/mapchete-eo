import logging
import numpy as np
import numpy.ma as ma
from rasterio.enums import Resampling
from typing import List

from mapchete_eo.platforms.sentinel2.driver import Sentinel2Cube


logger = logging.getLogger(__name__)


def execute(
    element84_sentinel2: Sentinel2Cube,
    assets: List[str],
    resampling: str = "bilinear",
    nodata: float = 0.0,
) -> ma.MaskedArray:
    """
    Create a temporal mean composite of cloud-free pixels.
    """
    logger.debug("Reading Sentinel-2 time series.")
    
    # Read all available products into an xarray dataset
    ds = element84_sentinel2.read(
        assets=assets,
        resampling=Resampling[resampling],
        nodatavals=nodata,
    )
    
    # Calculate mean over the time dimension
    # (Assuming xarray handle mask/nodata correctly via _FillValue)
    mean_composite = ds.mean(dim="time", skipna=True)
    
    # Convert back to numpy masked array
    # This is a simplified conversion for the example
    out_data = []
    out_mask = []
    for asset in assets:
        arr = mean_composite[asset].values
        out_data.append(arr)
        out_mask.append(np.isnan(arr))
        
    return ma.masked_array(
        data=np.stack(out_data).astype(np.uint16),
        mask=np.stack(out_mask)
    )
