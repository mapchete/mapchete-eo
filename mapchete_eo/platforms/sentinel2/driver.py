from typing import Union

from mapchete_eo import base
from mapchete_eo.platforms.sentinel2.config import Sentinel2DriverConfig
from mapchete_eo.platforms.sentinel2.product import S2Product
from mapchete_eo.types import MergeMethod

METADATA: dict = {
    "driver_name": "Sentinel-2",
    "data_type": None,
    "mode": "r",
    "file_extensions": [],
}


class InputTile(base.InputTile):
    # Sentinel-2 driver specific default values:
    default_read_merge_method: MergeMethod = MergeMethod.average
    default_read_nodataval: Union[int, None] = 0


class InputData(base.InputData):
    # Sentinel-2 driver specific parameters:
    default_product_cls = S2Product
    driver_config_model = Sentinel2DriverConfig
