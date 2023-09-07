"""
Contains all classes required to use the driver as mapchete input.
"""
import datetime
from typing import Union

from mapchete.path import MPath
from pydantic import BaseModel

from mapchete_eo import base
from mapchete_eo.archives.base import StaticArchive
from mapchete_eo.search.stac_static import STACStaticCatalog
from mapchete_eo.settings import DEFAULT_CATALOG_CRS

METADATA: dict = {
    "driver_name": "EOSTAC_DEV",
    "data_type": None,
    "mode": "r",
    "file_extensions": [],
}


class FormatParams(BaseModel):
    format: str
    start_time: Union[datetime.date, datetime.datetime]
    end_time: Union[datetime.date, datetime.datetime]
    cat_baseurl: str
    pattern: dict = {}


class InputTile(base.InputTile):
    """
    Target Tile representation of input data.

    Parameters
    ----------
    tile : ``Tile``
    kwargs : keyword arguments
        driver specific parameters
    """


class InputData(base.InputData):
    """In case this driver is used when being a readonly input to another process."""

    input_tile_cls = InputTile

    def __init__(self, input_params: dict, **kwargs) -> None:
        """Initialize."""
        super().__init__(input_params, **kwargs)
        format_params = FormatParams(**input_params["abstract"])
        self._bounds = input_params["delimiters"]["effective_bounds"]
        self.start_time = format_params.start_time
        self.end_time = format_params.end_time
        self.archive = StaticArchive(
            catalog=STACStaticCatalog(
                baseurl=MPath(format_params.cat_baseurl).absolute_path(
                    base_dir=input_params["conf_dir"]
                ),
                bounds=self.bbox(out_crs=DEFAULT_CATALOG_CRS).bounds,
                start_time=self.start_time,
                end_time=self.end_time,
                time_pattern=format_params.pattern,
            )
        )
