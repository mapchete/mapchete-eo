from __future__ import annotations

from typing import Any, List, Union

import numpy.ma as ma
import pystac
import xarray as xr
from mapchete.tile import BufferedTile
from mapchete.types import Bounds
from rasterio.enums import Resampling
from shapely.geometry import shape

from mapchete_eo.array.convert import masked_to_xarr
from mapchete_eo.io import get_item_property, item_to_np_array
from mapchete_eo.io.assets import eo_bands_to_assets_indexes
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
        resampling: Resampling = Resampling.nearest,
        nodatavals: NodataVals = None,
        x_axis_name: str = "x",
        y_axis_name: str = "y",
        **kwargs,
    ) -> xr.Dataset:
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
                        tile=tile,
                        resampling=resampling,
                        nodatavals=nodatavals,
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
        assets: Union[List[str], None] = None,
        eo_bands: Union[List[str], None] = None,
        tile: BufferedTile = None,
        resampling: Resampling = Resampling.nearest,
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

    def eo_bands_to_assets_indexes(self, eo_bands: List[str]) -> List[tuple]:
        return eo_bands_to_assets_indexes(self.item, eo_bands)
