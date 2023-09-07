from __future__ import annotations

import datetime
from typing import List, Union

import croniter
import numpy.ma as ma
import xarray as xr
from dateutil.tz import tzutc
from mapchete.formats import base
from mapchete.io.vector import reproject_geometry
from mapchete.tile import BufferedTile
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

from mapchete_eo.io import products_to_xarray
from mapchete_eo.product import EOProduct
from mapchete_eo.protocols import EOProductProtocol
from mapchete_eo.time import to_datetime
from mapchete_eo.types import MergeMethod


class InputTile(base.InputTile):
    """Target Tile representation of input data."""

    default_read_merge_method: MergeMethod = MergeMethod.average
    default_read_nodataval: Union[int, None] = 0

    tile: BufferedTile
    products: List[EOProductProtocol]
    eo_bands: dict
    start_time: Union[datetime.datetime, datetime.date]
    end_time: Union[datetime.datetime, datetime.date]

    def __init__(
        self,
        tile: BufferedTile,
        products: List[EOProductProtocol],
        eo_bands: dict,
        start_time: Union[datetime.datetime, datetime.date],
        end_time: Union[datetime.datetime, datetime.date],
        **kwargs,
    ) -> None:
        """Initialize."""
        self.tile = tile
        self.products = products
        self.eo_bands = eo_bands
        self.start_time = start_time
        self.end_time = end_time

    def read(
        self,
        assets: List[str] = [],
        eo_bands: List[str] = [],
        start_time: Union[str, datetime.datetime, None] = None,
        end_time: Union[str, datetime.datetime, None] = None,
        timestamps: Union[List[Union[str, datetime.datetime]], None] = None,
        time_pattern: Union[str, None] = None,
        merge_items_by: Union[str, None] = None,
        merge_method: Union[str, MergeMethod] = MergeMethod.first,
        **kwargs,
    ) -> xr.Dataset:
        """
        Read reprojected & resampled input data.

        Returns
        -------
        data : xarray.Dataset
        """
        # TODO: iterate through products, filter by time and read assets to window
        if any([start_time, end_time, timestamps]):
            raise NotImplementedError("time subsets are not yet implemented")
        if time_pattern:
            # filter products by time pattern
            tz = tzutc()
            coord_time = [
                t.replace(tzinfo=tz)
                for t in croniter.croniter_range(
                    to_datetime(self.start_time),
                    to_datetime(self.end_time),
                    time_pattern,
                )
            ]
            products = [
                product
                for product in self.products
                if product.item.datetime in coord_time
            ]
        else:
            products = self.products
        if len(products) == 0:
            return xr.Dataset()
        return products_to_xarray(
            products=products,
            eo_bands=eo_bands,
            assets=assets,
            tile=self.tile,
            **kwargs,
        )

    def read_levelled(
        self,
        target_height: int,
        assets: List[str] = [],
        eo_bands: List[str] = [],
        start_time: Union[str, datetime.datetime, None] = None,
        end_time: Union[str, datetime.datetime, None] = None,
        timestamps: Union[List[Union[str, datetime.datetime]], None] = None,
        time_pattern: Union[str, None] = None,
        merge_items_by: Union[str, None] = None,
        merge_method: Union[MergeMethod, str] = MergeMethod.average,
        **kwargs,
    ) -> ma.MaskedArray:
        raise NotImplementedError()

    def is_empty(self) -> bool:
        """
        Check if there is data within this tile.

        Returns
        -------
        is empty : bool
        """
        return len(self.items) == 0

    def _get_assets(self, indexes: Union[int, str, List[Union[int, str]], None] = None):
        if indexes is None:
            return list(range(len(self.eo_bands)))
        out = []
        for idx in indexes if isinstance(indexes, list) else [indexes]:
            if isinstance(idx, str):
                for band in self.eo_bands:
                    if idx == band.get("name"):
                        out.append(band.get("name"))
                        break
                else:
                    raise ValueError(f"cannot find eo:band asset name {idx}")
            elif isinstance(idx, int):
                out.append(self.eo_bands[idx - 1].get("name"))
            else:
                raise TypeError(
                    f"band index must either be an integer or a string: {idx}"
                )
        return out


class InputData(base.InputData):
    """In case this driver is used when being a readonly input to another process."""

    def bbox(self, out_crs: Union[str, None] = None) -> BaseGeometry:
        """
        Return data bounding box.

        Parameters
        ----------
        out_crs : ``rasterio.crs.CRS``
            rasterio CRS object (default: CRS of process pyramid)

        Returns
        -------
        bounding box : geometry
            Shapely geometry object
        """
        return reproject_geometry(
            box(*self._bounds),
            src_crs=self.pyramid.crs,
            dst_crs=self.pyramid.crs if out_crs is None else out_crs,
            segmentize_on_clip=True,
        )

    def open(self, tile: BufferedTile, **kwargs) -> InputTile:
        """
        Return InputTile object.

        Parameters
        ----------
        tile : ``Tile``

        Returns
        -------
        input tile : ``InputTile``
            tile view of input data
        """
        return self.input_tile_cls(
            tile,
            products=[
                EOProduct.from_stac_item(item)
                for item in self.archive.catalog.items.filter(
                    bounds=reproject_geometry(
                        tile.bbox, src_crs=tile.crs, dst_crs="EPSG:4326"
                    ).bounds
                )
            ],
            eo_bands=self.archive.catalog.eo_bands,
            start_time=self.start_time,
            end_time=self.end_time,
            **kwargs,
        )
