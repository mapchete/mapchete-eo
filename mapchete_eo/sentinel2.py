"""
Reader driver for Sentinel-2 data.


"""
import datetime
from enum import Enum
from mapchete.tile import BufferedTile
from pydantic import BaseModel
from typing import Union

from mapchete_eo import base
from mapchete_eo.known_catalogs import KnownCatalogs


class ProcessingLevel(Enum):
    """Available processing levels of Sentinel-2."""

    level1c = "L1C"
    level2a = "L2A"


class S2AWSCOGArchive:
    """
    Sentinel-2 COG archive on AWS maintained by Element84.

    URL: https://registry.opendata.aws/sentinel-2-l2a-cogs/
    """

    catalog = KnownCatalogs.earth_search_s2_cogs
    storage_options: dict = {
        # "baseurl": "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/"
    }


class S2AWSJP2Archive:
    """
    Sentinel-2 JPEG2000 archive on AWS maintained by Sinergise.

    This requires the requester pays setting.

    URL: https://registry.opendata.aws/sentinel-2/
    """

    catalog = KnownCatalogs.sinergise_s2
    storage_options: dict = {}


class KnownArchives(Enum):
    S2AWS_COG = S2AWSCOGArchive
    S2AWS_JP2 = S2AWSJP2Archive


class FormatParams(BaseModel):
    format: str = "Sentinel-2"
    level: ProcessingLevel = ProcessingLevel.level2a
    archive: KnownArchives = KnownArchives.S2AWS_COG
    start_time: Union[datetime.date, datetime.datetime]
    end_time: Union[datetime.date, datetime.datetime]


METADATA: dict = {
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
        format_params = dict_to_format_params(input_params["abstract"])
        self._bounds = input_params["delimiters"]["effective_bounds"]
        self.start_time = format_params.start_time
        self.end_time = format_params.end_time
        self.catalog = format_params.archive.value.catalog.value(
            bounds=self.bbox(out_crs=4326).bounds,
            start_time=self.start_time,
            end_time=self.end_time,
        )
        self.storage_options = format_params.archive.value.storage_options


def dict_to_format_params(format_params: dict) -> FormatParams:
    return FormatParams(**format_params)
