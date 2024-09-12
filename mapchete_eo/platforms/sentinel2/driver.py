from typing import Optional, List, Tuple

from mapchete.path import MPath
from mapchete.types import NodataVal
from rasterio.enums import Resampling

from mapchete_eo import base
from mapchete_eo.archives.base import StaticArchive
from mapchete_eo.platforms.sentinel2.config import Sentinel2DriverConfig
from mapchete_eo.platforms.sentinel2.preprocessing_tasks import parse_s2_product
from mapchete_eo.search.stac_static import STACStaticCatalog
from mapchete_eo.settings import mapchete_eo_settings
from mapchete_eo.types import MergeMethod

METADATA: dict = {
    "driver_name": "Sentinel-2",
    "data_type": None,
    "mode": "r",
    "file_extensions": [],
}


class Sentinel2Cube(base.EODataCube):
    # Sentinel-2 driver specific default values:
    default_read_merge_method: MergeMethod = MergeMethod.average
    default_read_merge_products_by: Optional[str] = "s2:datastrip_id"
    default_read_nodataval: NodataVal = 0
    default_read_resampling: Resampling = Resampling.bilinear


Sentinel2CubeGroup = List[Tuple[str, Sentinel2Cube]]


class InputData(base.InputData):
    # Sentinel-2 driver specific parameters:
    default_preprocessing_task = staticmethod(parse_s2_product)
    driver_config_model = Sentinel2DriverConfig
    params: Sentinel2DriverConfig
    input_tile_cls = Sentinel2Cube

    def set_archive(self, base_dir: MPath):
        if self.params.cat_baseurl:
            self.archive = StaticArchive(
                catalog=STACStaticCatalog(
                    baseurl=MPath(self.params.cat_baseurl).absolute_path(
                        base_dir=base_dir
                    ),
                    area=self.bbox(mapchete_eo_settings.default_catalog_crs),
                    time=self.time,
                )
            )
        elif self.params.archive:
            self.archive = self.params.archive(
                time=self.time,
                bounds=self.area.bounds,
                area=self.area,
                search_index=(
                    MPath(self.params.search_index).absolute_path(base_dir=base_dir)
                    if self.params.search_index
                    else None
                ),
            )
        else:
            raise ValueError("either 'archive' or 'cat_baseurl' or both is required.")
