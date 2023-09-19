from __future__ import annotations

from functools import cached_property
from typing import Any, List, Type, Union

import croniter
import numpy.ma as ma
import xarray as xr
from dateutil.tz import tzutc
from mapchete.formats import base
from mapchete.io.vector import IndexedFeatures, reproject_geometry
from mapchete.path import MPath
from mapchete.tile import BufferedTile
from pydantic import BaseModel
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

from mapchete_eo.archives.base import Archive, StaticArchive
from mapchete_eo.exceptions import PreprocessingNotFinished
from mapchete_eo.io import products_to_xarray
from mapchete_eo.product import EOProduct
from mapchete_eo.protocols import EOProductProtocol
from mapchete_eo.search.stac_static import STACStaticCatalog
from mapchete_eo.settings import DEFAULT_CATALOG_CRS
from mapchete_eo.time import to_datetime
from mapchete_eo.types import DateTimeLike, MergeMethod, NodataVal, NodataVals


class BaseDriverConfig(BaseModel):
    format: str
    start_time: DateTimeLike
    end_time: DateTimeLike
    cat_baseurl: Union[str, None] = None
    archive: Union[Type[Archive], None] = None
    pattern: dict = {}
    cache: Any = None


class InputTile(base.InputTile):
    """Target Tile representation of input data."""

    default_read_merge_method: MergeMethod = MergeMethod.first
    default_read_merge_products_by: Union[str, None] = None
    default_read_nodataval: NodataVal = None

    tile: BufferedTile
    eo_bands: dict
    start_time: DateTimeLike
    end_time: DateTimeLike

    def __init__(
        self,
        tile: BufferedTile,
        products: Union[List[EOProductProtocol], None],
        eo_bands: dict,
        start_time: DateTimeLike,
        end_time: DateTimeLike,
        input_key: Union[str, None] = None,
        **kwargs,
    ) -> None:
        """Initialize."""
        self.tile = tile
        self._products = products
        self.eo_bands = eo_bands
        self.start_time = start_time
        self.end_time = end_time
        self.input_key = input_key

    @cached_property
    def products(self) -> IndexedFeatures[EOProductProtocol]:
        # during task graph processing, the products have to be fetched as preprocessing task results
        if self._products is None:
            if not self.preprocessing_tasks_results:
                raise ValueError("no preprocessing results available")
            return IndexedFeatures(
                self.preprocessing_tasks_results.values(), crs=self.tile.crs
            )

        # just return the prouducts as is
        return IndexedFeatures(self._products, crs=self.tile.crs)

    def read(
        self,
        assets: List[str] = [],
        eo_bands: List[str] = [],
        start_time: Union[DateTimeLike, None] = None,
        end_time: Union[DateTimeLike, None] = None,
        timestamps: Union[List[DateTimeLike], None] = None,
        time_pattern: Union[str, None] = None,
        merge_products_by: Union[str, None] = None,
        merge_method: Union[str, MergeMethod, None] = None,
        nodatavals: NodataVals = None,
        **kwargs,
    ) -> xr.Dataset:
        """
        Read reprojected & resampled input data.

        Returns
        -------
        data : xarray.Dataset
        """
        # TODO: iterate through products, filter by time and read assets to window
        if any([start_time, end_time, timestamps]):
            raise NotImplementedError("time subsets are not yet implemented")

        if time_pattern:
            # filter products by time pattern
            tz = tzutc()
            coord_time = [
                t.replace(tzinfo=tz)
                for t in croniter.croniter_range(
                    to_datetime(self.start_time),
                    to_datetime(self.end_time),
                    time_pattern,
                )
            ]
            products = [
                product
                for product in self.products
                if product.item.datetime in coord_time
            ]
        else:
            products = self.products

        if len(products) == 0:
            return xr.Dataset()

        return products_to_xarray(
            products=products,
            eo_bands=eo_bands,
            assets=assets,
            grid=self.tile,
            merge_products_by=merge_products_by or self.default_read_merge_products_by,
            merge_method=merge_method or self.default_read_merge_method,
            nodatavals=self.default_read_nodataval
            if nodatavals is None
            else nodatavals,
        )

    def read_levelled(
        self,
        target_height: int,
        assets: List[str] = [],
        eo_bands: List[str] = [],
        start_time: Union[DateTimeLike, None] = None,
        end_time: Union[DateTimeLike, None] = None,
        timestamps: Union[List[DateTimeLike], None] = None,
        time_pattern: Union[str, None] = None,
        merge_items_by: Union[str, None] = None,
        merge_method: Union[MergeMethod, str] = MergeMethod.average,
        **kwargs,
    ) -> ma.MaskedArray:
        raise NotImplementedError()

    def is_empty(self) -> bool:
        """
        Check if there is data within this tile.

        Returns
        -------
        is empty : bool
        """
        return len(self.items) == 0


class InputData(base.InputData):
    default_product_cls = EOProduct
    driver_config_model: Type[BaseDriverConfig] = BaseDriverConfig
    params: BaseDriverConfig
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
        self.readonly = readonly
        self.input_key = input_key
        self.standalone = standalone

        self.params = self.driver_config_model(**input_params["abstract"])
        self._bounds = input_params["delimiters"]["effective_bounds"]
        self._area = input_params["delimiters"]["effective_area"]
        self.start_time = self.params.start_time
        self.end_time = self.params.end_time

        if self.readonly:
            return

        # set archive
        if self.params.cat_baseurl:
            self.archive = StaticArchive(
                catalog=STACStaticCatalog(
                    baseurl=MPath(self.params.cat_baseurl).absolute_path(
                        base_dir=input_params["conf_dir"]
                    ),
                    bounds=self.bbox(out_crs=DEFAULT_CATALOG_CRS).bounds,
                    start_time=self.start_time,
                    end_time=self.end_time,
                )
            )
        elif self.params.archive:
            self.archive = self.params.archive(
                start_time=self.start_time,
                end_time=self.end_time,
                bounds=self._bounds,
                area=self.area,
            )

        for item in self.archive.catalog.items:
            self.add_preprocessing_task(
                self.default_product_cls.from_stac_item,
                fargs=(item,),
                fkwargs=dict(cache_config=self.params.cache, cache_all=True),
                key=item.id,
                geometry=reproject_geometry(
                    item.geometry, src_crs=DEFAULT_CATALOG_CRS, dst_crs=self.crs
                ),
            )

    def bbox(self, out_crs: Union[str, None] = None) -> BaseGeometry:
        """Return data bounding box."""
        return reproject_geometry(
            box(*self._bounds),
            src_crs=self.pyramid.crs,
            dst_crs=self.pyramid.crs if out_crs is None else out_crs,
            segmentize_on_clip=True,
        )

    @cached_property
    def products(self) -> IndexedFeatures:
        """Hold preprocessed S2Products in an IndexedFeatures container."""

        # nothing to index here
        if self.readonly or not self.preprocessing_tasks:
            return IndexedFeatures([])

        # TODO: copied it from mapchete_satellite, not yet sure which use case this is
        elif self.standalone:
            raise NotImplementedError()

        # if preprocessing tasks are ready, index them for further use
        elif self.preprocessing_tasks_results:
            return IndexedFeatures(
                [
                    self.get_preprocessing_task_result(item.id)
                    for item in self.archive.catalog.items
                ],
                crs=self.crs,
            )

        # this happens on task graph execution when preprocessing task results are not ready
        else:
            raise PreprocessingNotFinished(
                f"products are not ready yet because {len(self.preprocessing_tasks)} preprocessing task(s) were not executed."
            )

    def open(self, tile, **kwargs) -> InputTile:
        """
        Return InputTile object.
        """
        try:
            tile_products = self.products.filter(tile.bounds)
        except PreprocessingNotFinished:
            tile_products = None
        return self.input_tile_cls(
            tile,
            products=tile_products,
            eo_bands=self.archive.catalog.eo_bands,
            start_time=self.start_time,
            end_time=self.end_time,
            # passing on the input key is essential so dependent preprocessing tasks can be found!
            input_key=self.input_key,
        )
