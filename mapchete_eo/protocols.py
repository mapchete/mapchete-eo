from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Tuple

import numpy.ma as ma
import pystac
import xarray as xr
from affine import Affine
from mapchete.types import Bounds
from rasterio.crs import CRS
from rasterio.enums import Resampling

from mapchete_eo.types import DateTimeLike, NodataVals


class EOProductProtocol(Protocol):
    item: pystac.Item
    bounds: Bounds
    crs: CRS
    __geo_interface__: Optional[Dict[str, Any]]

    @classmethod
    def from_stac_item(self, item: pystac.Item, **kwargs) -> EOProductProtocol:
        ...

    def read(
        self,
        assets: Optional[List[str]] = None,
        eo_bands: Optional[List[str]] = None,
        grid: Optional[GridProtocol] = None,
        resampling: Resampling = Resampling.nearest,
        nodatavals: NodataVals = None,
        x_axis_name: str = "x",
        y_axis_name: str = "y",
        **kwargs,
    ) -> xr.Dataset:
        ...

    def read_np_array(
        self,
        assets: Optional[List[str]] = None,
        eo_bands: Optional[List[str]] = None,
        grid: Optional[GridProtocol] = None,
        resampling: Resampling = Resampling.nearest,
        nodatavals: NodataVals = None,
        **kwargs,
    ) -> ma.MaskedArray:
        ...

    def get_property(self, property: str) -> Any:
        ...


class GridProtocol(Protocol):
    transform: Affine
    width: int
    height: int
    shape: Tuple[int, int]
    bounds: Bounds
    crs: CRS


class DateTimeProtocol(Protocol):
    datetime: DateTimeLike
