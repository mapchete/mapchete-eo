from __future__ import annotations

from typing import Any, List, Union

import numpy.ma as ma
import pystac
import xarray as xr
from mapchete.tile import BufferedTile
from mapchete.types import Bounds
from rasterio.crs import CRS
from shapely.geometry import shape

from mapchete_eo.io import get_item_property, item_to_np_array, item_to_xarray
from mapchete_eo.protocols import EOProductProtocol
from mapchete_eo.settings import DEFAULT_CATALOG_CRS
from mapchete_eo.types import NodataVals


class EOProduct(EOProductProtocol):
    """Wrapper class around a pystac.Item which provides read functions."""

    def __init__(self, item: pystac.Item):
        self.item = item
        self.__geo_interface__ = self.item.geometry
        self.bounds = Bounds.from_inp(shape(self))
        self.crs = DEFAULT_CATALOG_CRS

    def __repr__(self):
        return f"<EOProduct product_id={self.item.id}>"

    @classmethod
    def from_stac_item(self, item: pystac.Item, **kwargs) -> EOProduct:
        return EOProduct(item)

    def read(
        self,
        assets: Union[List[str], None] = None,
        eo_bands: Union[List[str], None] = None,
        tile: BufferedTile = None,
        resampling: Union[List[str], str] = "nearest",
        nodatavals: NodataVals = None,
        x_axis_name: str = "x",
        y_axis_name: str = "y",
        time_axis_name: str = "time",
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
            time_axis_name=time_axis_name,
        )

    def read_np_array(
        self,
        assets: Union[List[str], None] = None,
        eo_bands: Union[List[str], None] = None,
        tile: BufferedTile = None,
        resampling: Union[List[str], str] = "nearest",
        nodatavals: NodataVals = None,
        **kwargs,
    ) -> ma.MaskedArray:
        return item_to_np_array(
            self.item,
            assets=assets or [],
            eo_bands=eo_bands or [],
            tile=tile,
            resampling=resampling,
            nodatavals=nodatavals,
        )

    def get_property(self, property: str) -> Any:
        return get_item_property(self.item, property)
