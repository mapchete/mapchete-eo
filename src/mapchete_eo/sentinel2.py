"""
Reader driver for Sentinel-2 data.
"""
import datetime

import xarray as xr
from mapchete.tile import BufferedTile

from mapchete_eo import base
from mapchete_eo.known_catalogs import E84Sentinel2COGs

METADATA = {
    "driver_name": "Sentinel-2",
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


class InputData(base.InputData):
    """In case this driver is used when being a readonly input to another process."""

    input_tile_cls = InputTile

    def __init__(self, input_params: dict, **kwargs) -> None:
        """Initialize."""
        super().__init__(input_params, **kwargs)
        format_params = input_params["abstract"]
        self._bounds = input_params["delimiters"]["effective_bounds"]
        self.start_time = format_params["start_time"]
        self.end_time = format_params["end_time"]

        self.catalog = E84Sentinel2COGs(
            bounds=self.bbox(out_crs=4326).bounds,
            start_time=self.start_time,
            end_time=self.end_time,
        )
