from typing import Union, Optional, List

from mapchete.types import MPathLike

from mapchete_eo import base
from mapchete_eo.search.config import StacSearchConfig

from mapchete_eo.source import Source
from mapchete_eo.types import TimeRange

from mapchete_eo.source_config import KNOWN_SOURCES

"""
Driver class for EOSTAC static STAC catalogs.
"""

METADATA: dict = {
    "driver_name": "EOSTAC",
    "data_type": None,
    "mode": "r",
    "file_extensions": [],
}

default_source = Source.model_validate(KNOWN_SOURCES["EarthSearch"])


class InputTile(base.EODataCube):
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

    format: str = "EOSTAC"
    time: Optional[Union[TimeRange, List[TimeRange]]] = None

    # new
    source: List[Source] = [default_source]

    # deprecated
    # for backwards compatibility, archive should be converted to
    # catalog & data_archive
    # archive: ArchiveClsFromString = AWSL2ACOGv1

    # don't know yet how to handle this
    cat_baseurl: Optional[MPathLike] = None
    search_index: Optional[MPathLike] = None

    # custom params
    stac_config: StacSearchConfig = StacSearchConfig()
