from __future__ import annotations

import logging
from typing import Any, List, Optional, Union

import numpy as np
import numpy.ma as ma
import pystac
import xarray as xr
from mapchete import Timer
from mapchete.types import Bounds
from numpy.typing import DTypeLike
from rasterio.enums import Resampling
from shapely.geometry import shape

from mapchete_eo.array.convert import masked_to_xarr
from mapchete_eo.exceptions import EmptyProductException
from mapchete_eo.io import get_item_property, item_to_np_array
from mapchete_eo.io.assets import eo_bands_to_assets_indexes
from mapchete_eo.protocols import EOProductProtocol, GridProtocol
from mapchete_eo.settings import DEFAULT_CATALOG_CRS
from mapchete_eo.types import NodataVals

logger = logging.getLogger(__name__)


class EOProduct(EOProductProtocol):
    """Wrapper class around a pystac.Item which provides read functions."""

    default_dtype: DTypeLike = np.uint16

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
        assets: Optional[List[str]] = None,
        eo_bands: Optional[List[str]] = None,
        grid: Union[GridProtocol, None] = None,
        resampling: Resampling = Resampling.nearest,
        nodatavals: NodataVals = None,
        x_axis_name: str = "x",
        y_axis_name: str = "y",
        raise_empty: bool = True,
        **kwargs,
    ) -> xr.Dataset:
        """Read bands and assets into xarray."""
        # developer info: all fancy stuff for special platforms like Sentinel-2
        # should be implemented in the respective read_np_array() methods which get
        # called by this method. No need to apply masks etc. here too.
        assets = assets or []
        eo_bands = eo_bands or []
        if eo_bands:
            assets_indexes = self.eo_bands_to_assets_indexes(eo_bands)
            data_var_names = eo_bands
        elif assets:
            assets_indexes = [(asset, 1) for asset in assets]
            data_var_names = assets
        else:
            raise ValueError("either eo_bands or assets have to be provided")

        return xr.Dataset(
            data_vars={
                data_var_name: masked_to_xarr(
                    asset_arr,
                    x_axis_name=x_axis_name,
                    y_axis_name=y_axis_name,
                    name=asset,
                    attrs=dict(item_id=self.item.id),
                )
                for asset_arr, data_var_name, (asset, _), in zip(
                    self.read_np_array(
                        assets=assets,
                        eo_bands=eo_bands,
                        grid=grid,
                        resampling=resampling,
                        nodatavals=nodatavals,
                        raise_empty=raise_empty,
                        **kwargs,
                    ),
                    data_var_names,
                    assets_indexes,
                )
            },
            coords={},
            attrs=dict(
                self.item.properties,
                id=self.item.id,
            ),
        )

    def read_np_array(
        self,
        assets: Optional[List[str]] = None,
        eo_bands: Optional[List[str]] = None,
        grid: Union[GridProtocol, Any] = None,
        resampling: Resampling = Resampling.nearest,
        nodatavals: NodataVals = None,
        raise_empty: bool = True,
        **kwargs,
    ) -> ma.MaskedArray:
        assets = assets or []
        eo_bands = eo_bands or []
        bands = assets or eo_bands
        logger.debug("%s: reading assets %s over %s", self, bands, grid)
        with Timer() as t:
            out = item_to_np_array(
                self.item,
                assets=assets,
                eo_bands=eo_bands,
                grid=grid,
                resampling=resampling,
                nodatavals=nodatavals,
                raise_empty=raise_empty,
            )
        logger.debug("%s: read in %s", self, t)
        return out

    def empty_array(
        self,
        count: int,
        grid: GridProtocol,
        fill_value: int = 0,
        dtype: Optional[DTypeLike] = None,
    ) -> ma.MaskedArray:
        shape = (count, *grid.shape)
        dtype = dtype or self.default_dtype
        return ma.MaskedArray(
            data=np.full(shape, fill_value=fill_value, dtype=dtype),
            mask=np.ones(shape, dtype=bool),
            fill_value=fill_value,
        )

    def get_property(self, property: str) -> Any:
        return get_item_property(self.item, property)

    def eo_bands_to_assets_indexes(self, eo_bands: List[str]) -> List[tuple]:
        return eo_bands_to_assets_indexes(self.item, eo_bands)
