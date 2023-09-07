from __future__ import annotations

from typing import List, Union

import numpy.ma as ma
import pystac
import xarray as xr
from mapchete.tile import BufferedTile
from mapchete.types import Bounds
from rasterio.crs import CRS

from mapchete_eo.io import item_to_xarray
from mapchete_eo.protocols import EOProductProtocol


class EOProduct(EOProductProtocol):
    """Wrapper class around a pystac.Item which provides read functions."""

    item: pystac.Item
    bounds: Bounds
    crs: CRS

    def __init__(self, item: pystac.Item):
        self.item = item

    @classmethod
    def from_stac_item(self, item: pystac.Item, **kwargs) -> EOProduct:
        return EOProduct(item)

    def read(
        self,
        assets: Union[List[str], None] = None,
        eo_bands: Union[List[str], None] = None,
        tile: BufferedTile = None,
        resampling: Union[List[str], str] = "nearest",
        nodatavals: Union[List[float], List[None], float, None] = None,
        x_axis_name: str = "x",
        y_axis_name: str = "y",
        **kwargs,
    ) -> xr.Dataset:
        return item_to_xarray(
            self.item,
            assets=assets or [],
            eo_bands=eo_bands or [],
            tile=tile,
            resampling=resampling,
            nodatavals=nodatavals,
            x_axis_name=x_axis_name,
            y_axis_name=y_axis_name,
        )

    def read_ma(
        self, assets: Union[list, None] = None, resampling="nearest", **kwargs
    ) -> ma.MaskedArray:
        raise NotImplementedError()
