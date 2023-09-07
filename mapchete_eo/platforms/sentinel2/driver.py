from functools import cached_property
from typing import Union

from mapchete.io.vector import IndexedFeatures, reproject_geometry
from mapchete.path import MPath

from mapchete_eo import base
from mapchete_eo.archives.base import Archive, StaticArchive
from mapchete_eo.platforms.sentinel2.config import DriverConfig
from mapchete_eo.platforms.sentinel2.product import S2Product
from mapchete_eo.search.stac_static import STACStaticCatalog
from mapchete_eo.types import MergeMethod

# here is everything we need to configure and initialize the mapchete driver
############################################################################

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

    default_read_merge_method: MergeMethod = MergeMethod.average
    default_read_nodataval: Union[int, None] = 0


class InputData(base.InputData):
    """In case this driver is used when being a readonly input to another process."""

    archive: Archive

    def __init__(
        self,
        input_params: dict,
        readonly: bool = False,
        input_key: Union[str, None] = None,
        standalone: bool = False,
        **kwargs,
    ) -> None:
        """Initialize."""
        super().__init__(input_params, **kwargs)
        format_params = DriverConfig(**input_params["abstract"])
        self._bounds = input_params["delimiters"]["effective_bounds"]
        self.start_time = format_params.start_time
        self.end_time = format_params.end_time
        if format_params.cat_baseurl:
            self.archive = StaticArchive(
                catalog=STACStaticCatalog(
                    baseurl=MPath(format_params.cat_baseurl).absolute_path(
                        base_dir=input_params["conf_dir"]
                    ),
                    bounds=self.bbox(out_crs="EPSG:4326").bounds,
                    start_time=self.start_time,
                    end_time=self.end_time,
                )
            )
        else:
            self.archive = format_params.archive(
                self.start_time, self.end_time, self._bounds
            )
        self.readonly = readonly
        self.input_key = input_key
        self.standalone = standalone
        if not self.readonly:
            for item in self.archive.catalog.items:
                self.add_preprocessing_task(
                    S2Product.from_stac_item,
                    fargs=(item,),
                    fkwargs=dict(cache_config=format_params.cache, cache_all=True),
                    key=item.id,
                    geometry=reproject_geometry(
                        item.geometry, src_crs="EPSG:4326", dst_crs=self.crs
                    ),
                )

    @cached_property
    def products(self) -> IndexedFeatures:
        """Hold preprocessed S2Products in an IndexedFeatures container."""
        if self.readonly:
            return IndexedFeatures([])
        if self.standalone:
            raise NotImplementedError()
        return IndexedFeatures(
            [
                self.get_preprocessing_task_result(item.id)
                for item in self.archive.catalog.items
            ],
            crs=self.crs,
        )

    def open(self, tile, **kwargs) -> InputTile:
        """
        Return InputTile object.
        """
        return InputTile(
            tile,
            products=self.products.filter(tile.bounds),
            eo_bands=self.archive.catalog.eo_bands,
            start_time=self.start_time,
            end_time=self.end_time,
        )
