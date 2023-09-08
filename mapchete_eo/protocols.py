from __future__ import annotations

from typing import Any, Dict, List, Protocol, Union

import pystac
import xarray as xr
from mapchete.tile import BufferedTile
from mapchete.types import Bounds
from rasterio.crs import CRS
from rasterio.enums import Resampling

from mapchete_eo.types import NodataVals


class EOProductProtocol(Protocol):
    item: pystac.Item
    bounds: Bounds
    crs: CRS
    __geo_interface__: Union[Dict[str, Any], None]

    @classmethod
    def from_stac_item(self, item: pystac.Item, **kwargs) -> EOProductProtocol:
        ...

    def read(
        self,
        assets: Union[List[str], None] = None,
        eo_bands: Union[List[str], None] = None,
        tile: BufferedTile = None,
        resampling: Resampling = Resampling.nearest,
        nodatavals: NodataVals = None,
        x_axis_name: str = "x",
        y_axis_name: str = "y",
        **kwargs,
    ) -> xr.Dataset:
        ...

    def get_property(self, property: str) -> Any:
        ...
