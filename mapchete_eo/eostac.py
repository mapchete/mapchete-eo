"""
Driver class for EOSTAC static STAC catalogs.
"""

from mapchete_eo import base

METADATA: dict = {
    "driver_name": "EOSTAC_DEV",
    "data_type": None,
    "mode": "r",
    "file_extensions": [],
}


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
