import croniter
import datetime
from dateutil.tz import tzutc
import xarray as xr
from mapchete.formats import base
from mapchete.io.vector import reproject_geometry
from mapchete.tile import BufferedTile
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry
from typing import List, Union

from mapchete_eo.io import items_to_xarray, MergeMethod


class InputTile(base.InputTile):
    """
    Target Tile representation of input data.

    Parameters
    ----------
    tile : ``Tile``
    kwargs : keyword arguments
        driver specific parameters
    """

    def read(
        self,
        assets: List[str] = [],
        eo_bands: List[str] = [],
        start_time: Union[str, datetime.datetime, None] = None,
        end_time: Union[str, datetime.datetime, None] = None,
        timestamps: Union[List[Union[str, datetime.datetime]], None] = None,
        time_pattern: Union[str, None] = None,
        **kwargs,
    ) -> xr.Dataset:
        """
        Read reprojected & resampled input data.

        Returns
        -------
        data : xarray.Dataset
        """
        # TODO: iterate through items, filter by time and read assets to window
        if any([start_time, end_time, timestamps]):
            raise NotImplementedError("time subsets are not yet implemented")
        if time_pattern:
            # filter items by time pattern
            tz = tzutc()
            coord_time = [
                t.replace(tzinfo=tz)
                for t in croniter.croniter_range(
                    self.start_time,
                    self.end_time,
                    time_pattern,
                )
            ]
            items = [i for i in self.items if i.datetime in coord_time]
        else:
            items = self.items
        if len(items) == 0:
            return xr.Dataset()
        return items_to_xarray(
            items=items, eo_bands=eo_bands, assets=assets, tile=self.tile, **kwargs
        )

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
            items=self.archive.catalog.items.filter(
                bounds=reproject_geometry(
                    tile.bbox, src_crs=tile.crs, dst_crs="EPSG:4326"
                ).bounds
            ),
            eo_bands=self.archive.catalog.eo_bands,
            start_time=self.start_time,
            end_time=self.end_time,
            **kwargs,
        )
