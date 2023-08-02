"""
Reader driver for Sentinel-2 data.
"""
import datetime
from enum import Enum
from mapchete.tile import BufferedTile
from pydantic import BaseModel
from typing import Type, Union

from mapchete_eo import base
from mapchete_eo.archives.base import Archive
from mapchete_eo.known_catalogs import EarthSearchV1S2L2A
from mapchete_eo.platforms.sentinel2.types import ProcessingLevel

from mapchete_eo.platforms.sentinel2.metadata_parser import S2Metadata
from mapchete_eo.platforms.sentinel2.path_mappers import (
    s2path_mapper_guesser,
    EarthSearchPathMapper,
)
from mapchete_eo.platforms.sentinel2.metadata_parser import s2metadata_from_stac_item

# this is important to add all path mappers defined here to the automated constructor
S2Metadata.path_mapper_guesser = s2path_mapper_guesser
# this is important to properly parse incoming pystac Items
S2Metadata.from_stac_item_constructor = s2metadata_from_stac_item


# below all supported archives are defined
##########################################


class AWSL2ACOGv1(Archive):
    catalog_cls = EarthSearchV1S2L2A
    collection_name = "sentinel-2-l2a"
    processing_level = ProcessingLevel.level2a
    path_mapper_cls = EarthSearchPathMapper


class KnownArchives(Enum):
    S2AWS_COG = AWSL2ACOGv1


# here is everything we need to configure and initialize the mapchete driver
############################################################################


class FormatParams(BaseModel):
    format: str = "Sentinel-2"
    archive: Type[Archive] = KnownArchives.S2AWS_COG.value
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
        self.archive = format_params.archive(
            self.start_time, self.end_time, self._bounds
        )


def dict_to_format_params(format_params: dict) -> FormatParams:
    return FormatParams(**format_params)
