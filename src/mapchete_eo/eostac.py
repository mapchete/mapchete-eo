"""
Contains all classes required to use the driver as mapchete input.
"""
import datetime

import xarray as xr
from mapchete.formats import base
from mapchete.io import absolute_path
from mapchete.io.vector import reproject_geometry
from mapchete.tile import BufferedTile
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

from mapchete_eo.discovery.stac_static import StaticSTACCatalog

METADATA = {
    "driver_name": "EOSTAC",
    "data_type": None,
    "mode": "r",
    "file_extensions": [],
}


class InputTile(base.InputTile):
    """
    Target Tile representation of input data.

    Parameters
    ----------
    tile : ``Tile``
    kwargs : keyword arguments
        driver specific parameters
    """

    def __init__(
        self,
        tile: BufferedTile,
        items: list,
        eo_bands: list,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        **kwargs,
    ) -> None:
        """Initialize."""
        self.tile = tile
        self.items = items
        self.eo_bands = eo_bands
        self.start_time = start_time
        self.end_time = end_time

    def read(
        self, indexes=None, start_time=None, end_time=None, timestamps=None, **kwargs
    ) -> xr.Dataset:
        """
        Read reprojected & resampled input data.

        Returns
        -------
        data : xarray.Dataset
        """
        # assets = self._get_assets(indexes)
        # TODO: iterate through items, filter by time and read assets to window
        # generate an array with the following axes:
        # (time/product_id, band, x, y)
        # coords = {self.time_axis_name: input_data_tiles[0][1].time.values}
        # return xr.Dataset(
        #     data_vars={
        #         band_name: (self.axis_names, band)
        #         for band_name, band in zip(self.band_names, arr)
        #     },
        #     coords=coords,
        # )
        raise NotImplementedError()

    def is_empty(self) -> bool:
        """
        Check if there is data within this tile.

        Returns
        -------
        is empty : bool
        """
        raise NotImplementedError()

    def _get_assets(self, indexes=None):
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
                out.append(self.eo_bands[idx].get("name"))
            else:
                raise TypeError(
                    f"band index must either be an integer or a string: {idx}"
                )
        return out


class InputData(base.InputData):
    """In case this driver is used when being a readonly input to another process."""

    def __init__(self, input_params: dict, **kwargs) -> None:
        """Initialize."""
        super().__init__(input_params, **kwargs)
        format_params = input_params["abstract"]
        if "cat_baseurl" not in format_params:
            raise ValueError("cat_baseurl is missing from config")
        self._bounds = input_params["delimiters"]["effective_bounds"]
        self.start_time = format_params["start_time"]
        self.end_time = format_params["end_time"]
        self.catalog = StaticSTACCatalog(
            baseurl=absolute_path(
                path=format_params["cat_baseurl"], base_dir=input_params["conf_dir"]
            ),
            bounds=self.bbox(out_crs=4326).bounds,
            start_time=self.start_time,
            end_time=self.end_time,
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
        return InputTile(
            tile,
            items=self.catalog.items.filter(bounds=tile.bounds),
            eo_bands=self.catalog.eo_bands,
            start_time=self.start_time,
            end_time=self.end_time,
            **kwargs,
        )

    def bbox(self, out_crs=None) -> BaseGeometry:
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
