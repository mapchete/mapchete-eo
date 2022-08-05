"""
Contains all classes required to use the driver as mapchete input.
"""
import datetime

from mapchete.io import absolute_path
from mapchete.tile import BufferedTile

from mapchete_eo import base
from mapchete_eo.search.stac_static import STACStaticCatalog

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


class InputData(base.InputData):
    """In case this driver is used when being a readonly input to another process."""

    input_tile_cls = InputTile

    def __init__(self, input_params: dict, **kwargs) -> None:
        """Initialize."""
        super().__init__(input_params, **kwargs)
        format_params = input_params["abstract"]
        if "cat_baseurl" not in format_params:
            raise ValueError("cat_baseurl is missing from config")
        self._bounds = input_params["delimiters"]["effective_bounds"]
        self.start_time = format_params["start_time"]
        self.end_time = format_params["end_time"]
        self.catalog = STACStaticCatalog(
            baseurl=absolute_path(
                path=format_params["cat_baseurl"], base_dir=input_params["conf_dir"]
            ),
            bounds=self.bbox(out_crs=4326).bounds,
            start_time=self.start_time,
            end_time=self.end_time,
        )
