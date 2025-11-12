from __future__ import annotations

import warnings
import logging
from functools import cached_property
from typing import Any, Callable, List, Optional, Sequence, Type, Union, Dict, Generator

import croniter
from mapchete import Bounds
import numpy as np
import numpy.ma as ma
import xarray as xr
from dateutil.tz import tzutc
from mapchete.config.parse import guess_geometry
from mapchete.formats import base
from mapchete.geometry import reproject_geometry
from mapchete.io.vector import IndexedFeatures
from mapchete.path import MPath
from mapchete.tile import BufferedTile
from mapchete.types import MPathLike, NodataVal, NodataVals
from pydantic import BaseModel, model_validator
from pystac import Item
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

from mapchete_eo.exceptions import CorruptedProductMetadata, PreprocessingNotFinished
from mapchete_eo.io import (
    products_to_np_array,
    products_to_xarray,
    read_levelled_cube_to_np_array,
    read_levelled_cube_to_xarray,
)
from mapchete_eo.source import Source
from mapchete_eo.product import EOProduct
from mapchete_eo.protocols import EOProductProtocol
from mapchete_eo.settings import mapchete_eo_settings
from mapchete_eo.sort import SortMethodConfig, TargetDateSort
from mapchete_eo.time import to_datetime
from mapchete_eo.types import DateTimeLike, MergeMethod, TimeRange

logger = logging.getLogger(__name__)


class BaseDriverConfig(BaseModel):
    format: str
    source: Sequence[Source]
    time: Optional[Union[TimeRange, List[TimeRange]]] = None
    cat_baseurl: Optional[str] = None
    cache: Optional[Any] = None
    footprint_buffer: float = 0
    area: Optional[Union[MPathLike, dict, type[BaseGeometry]]] = None
    preprocessing_tasks: bool = False
    search_kwargs: Optional[Dict[str, Any]] = None

    @model_validator(mode="before")
    def to_list(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Expands source to list."""
        for field in ["source"]:
            value = values.get(field)
            if value is not None and not isinstance(value, list):
                values[field] = [value]
        return values

    @model_validator(mode="before")
    def deprecate_cat_baseurl(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        cat_baseurl = values.get("cat_baseurl")
        if cat_baseurl:  # pragma: no cover
            warnings.warn(
                "'cat_baseurl' will be deprecated soon. Please use 'catalog_type=static' in the source.",
                category=DeprecationWarning,
                stacklevel=2,
            )
            if values.get("source", []):
                raise ValueError(
                    "deprecated cat_baseurl field found alongside sources."
                )
            values["source"] = [dict(collection=cat_baseurl, catalog_type="static")]
        return values


class EODataCube(base.InputTile):
    """Target Tile representation of input data."""

    default_read_merge_method: MergeMethod = MergeMethod.first
    default_read_merge_products_by: Optional[str] = None
    default_read_nodataval: NodataVal = None
    default_read_resampling: Resampling = Resampling.nearest

    tile: BufferedTile
    eo_bands: dict
    time: Optional[List[TimeRange]]
    area: BaseGeometry
    area_pixelbuffer: int = 0

    def __init__(
        self,
        tile: BufferedTile,
        products: Optional[List[EOProductProtocol]],
        eo_bands: dict,
        time: Optional[List[TimeRange]] = None,
        input_key: Optional[str] = None,
        area: Optional[BaseGeometry] = None,
        **kwargs,
    ) -> None:
        """Initialize."""
        self.tile = tile
        self._products = products
        self.eo_bands = eo_bands
        self.time = time
        self.input_key = input_key
        self.area = tile.bbox if area is None else area

    @cached_property
    def products(self) -> IndexedFeatures[EOProductProtocol]:
        # during task graph processing, the products have to be fetched as preprocessing task results
        if self._products is None:  # pragma: no cover
            return IndexedFeatures(
                [
                    item
                    for item in self.preprocessing_tasks_results.values()
                    if not isinstance(item, CorruptedProductMetadata)
                ],
                crs=self.tile.crs,
                # by not using rtree, we avoid an edge case where products outside of process CRS bounds
                # cause rtree to fail when indexing the products.
                index=None,
            )

        # just return the prouducts as is
        return IndexedFeatures(
            [
                item
                for item in self._products
                if not isinstance(item, CorruptedProductMetadata)
            ],
            crs=self.tile.crs,
            # by not using rtree, we avoid an edge case where products outside of process CRS bounds
            # cause rtree to fail when indexing the products.
            index=None,
        )

    def read(
        self,
        assets: Optional[List[str]] = None,
        eo_bands: Optional[List[str]] = None,
        start_time: Optional[DateTimeLike] = None,
        end_time: Optional[DateTimeLike] = None,
        timestamps: Optional[List[DateTimeLike]] = None,
        time_pattern: Optional[str] = None,
        resampling: Optional[Union[Resampling, str]] = None,
        merge_products_by: Optional[str] = None,
        merge_method: Optional[MergeMethod] = None,
        sort: Optional[SortMethodConfig] = None,
        nodatavals: NodataVals = None,
        raise_empty: bool = True,
        **kwargs,
    ) -> xr.Dataset:
        """
        Read reprojected & resampled input data.

        Returns
        -------
        data : xarray.Dataset
        """
        return products_to_xarray(
            products=self.filter_products(
                start_time=start_time,
                end_time=end_time,
                timestamps=timestamps,
                time_pattern=time_pattern,
            ),
            eo_bands=eo_bands,
            assets=assets,
            grid=self.tile,
            raise_empty=raise_empty,
            product_read_kwargs=kwargs,
            sort=sort,
            **self.default_read_values(
                merge_products_by=merge_products_by,
                merge_method=merge_method,
                resampling=resampling,
                nodatavals=nodatavals,
            ),
        )

    def read_np_array(
        self,
        assets: Optional[List[str]] = None,
        eo_bands: Optional[List[str]] = None,
        start_time: Optional[DateTimeLike] = None,
        end_time: Optional[DateTimeLike] = None,
        timestamps: Optional[List[DateTimeLike]] = None,
        time_pattern: Optional[str] = None,
        resampling: Optional[Union[Resampling, str]] = None,
        merge_products_by: Optional[str] = None,
        merge_method: Optional[MergeMethod] = None,
        sort: Optional[SortMethodConfig] = None,
        nodatavals: NodataVals = None,
        raise_empty: bool = True,
        **kwargs,
    ) -> ma.MaskedArray:
        return products_to_np_array(
            products=self.filter_products(
                start_time=start_time,
                end_time=end_time,
                timestamps=timestamps,
                time_pattern=time_pattern,
            ),
            eo_bands=eo_bands,
            assets=assets,
            grid=self.tile,
            product_read_kwargs=kwargs,
            raise_empty=raise_empty,
            sort=sort,
            **self.default_read_values(
                merge_products_by=merge_products_by,
                merge_method=merge_method,
                resampling=resampling,
                nodatavals=nodatavals,
            ),
        )

    def read_levelled(
        self,
        target_height: int,
        assets: Optional[List[str]] = None,
        eo_bands: Optional[List[str]] = None,
        start_time: Optional[DateTimeLike] = None,
        end_time: Optional[DateTimeLike] = None,
        timestamps: Optional[List[DateTimeLike]] = None,
        time_pattern: Optional[str] = None,
        resampling: Optional[Union[Resampling, str]] = None,
        nodatavals: NodataVals = None,
        merge_products_by: Optional[str] = None,
        merge_method: Optional[MergeMethod] = None,
        sort: SortMethodConfig = TargetDateSort(),
        raise_empty: bool = True,
        slice_axis_name: str = "layers",
        band_axis_name: str = "bands",
        x_axis_name: str = "x",
        y_axis_name: str = "y",
        **kwargs,
    ) -> xr.Dataset:
        return read_levelled_cube_to_xarray(
            products=self.filter_products(
                start_time=start_time,
                end_time=end_time,
                timestamps=timestamps,
                time_pattern=time_pattern,
            ),
            target_height=target_height,
            assets=assets,
            eo_bands=eo_bands,
            grid=self.tile,
            raise_empty=raise_empty,
            product_read_kwargs=kwargs,
            slice_axis_name=slice_axis_name,
            band_axis_name=band_axis_name,
            x_axis_name=x_axis_name,
            y_axis_name=y_axis_name,
            sort=sort,
            **self.default_read_values(
                merge_products_by=merge_products_by,
                merge_method=merge_method,
                resampling=resampling,
                nodatavals=nodatavals,
            ),
        )

    def read_levelled_np_array(
        self,
        target_height: int,
        assets: Optional[List[str]] = None,
        eo_bands: Optional[List[str]] = None,
        start_time: Optional[DateTimeLike] = None,
        end_time: Optional[DateTimeLike] = None,
        timestamps: Optional[List[DateTimeLike]] = None,
        time_pattern: Optional[str] = None,
        resampling: Optional[Union[Resampling, str]] = None,
        nodatavals: NodataVals = None,
        merge_products_by: Optional[str] = None,
        merge_method: Optional[MergeMethod] = None,
        sort: SortMethodConfig = TargetDateSort(),
        raise_empty: bool = True,
        **kwargs,
    ) -> ma.MaskedArray:
        return read_levelled_cube_to_np_array(
            products=self.filter_products(
                start_time=start_time,
                end_time=end_time,
                timestamps=timestamps,
                time_pattern=time_pattern,
            ),
            target_height=target_height,
            assets=assets,
            eo_bands=eo_bands,
            grid=self.tile,
            raise_empty=raise_empty,
            product_read_kwargs=kwargs,
            sort=sort,
            **self.default_read_values(
                merge_products_by=merge_products_by,
                merge_method=merge_method,
                resampling=resampling,
                nodatavals=nodatavals,
            ),
        )

    def read_masks(
        self,
        start_time: Optional[DateTimeLike] = None,
        end_time: Optional[DateTimeLike] = None,
        timestamps: Optional[List[DateTimeLike]] = None,
        time_pattern: Optional[str] = None,
        nodatavals: NodataVals = None,
        **kwargs,
    ):
        from mapchete_eo.platforms.sentinel2.masks import read_masks

        return read_masks(
            products=self.filter_products(
                start_time=start_time,
                end_time=end_time,
                timestamps=timestamps,
                time_pattern=time_pattern,
            ),
            grid=self.tile,
            nodatavals=nodatavals,
            product_read_kwargs=kwargs,
        )

    def filter_products(
        self,
        start_time: Optional[DateTimeLike] = None,
        end_time: Optional[DateTimeLike] = None,
        timestamps: Optional[List[DateTimeLike]] = None,
        time_pattern: Optional[str] = None,
    ):
        """
        Return a filtered list of input products.
        """
        if any([start_time, end_time, timestamps]):  # pragma: no cover
            raise NotImplementedError("time subsets are not yet implemented")

        if time_pattern:
            # filter products by time pattern
            return [
                product
                for product in self.products
                if product.item.datetime
                in [
                    t.replace(tzinfo=tzutc())
                    for t in croniter.croniter_range(
                        to_datetime(self.start_time),
                        to_datetime(self.end_time),
                        time_pattern,
                    )
                ]
            ]
        return self.products

    def is_empty(self) -> bool:  # pragma: no cover
        """
        Check if there is data within this tile.

        Returns
        -------
        is empty : bool
        """
        return len(self.products) == 0

    def default_read_values(
        self,
        resampling: Optional[Union[Resampling, str]] = None,
        nodatavals: NodataVals = None,
        merge_products_by: Optional[str] = None,
        merge_method: Optional[MergeMethod] = None,
    ) -> dict:
        """Provide proper read values depending on user input and defaults."""
        if nodatavals is None:
            nodatavals = self.default_read_nodataval
        merge_products_by = merge_products_by or self.default_read_merge_products_by
        merge_method = merge_method or self.default_read_merge_method
        return dict(
            resampling=(
                self.default_read_resampling
                if resampling is None
                else (
                    resampling
                    if isinstance(resampling, Resampling)
                    else Resampling[resampling]
                )
            ),
            nodatavals=nodatavals,
            merge_products_by=merge_products_by,
            merge_method=merge_method,
            read_mask=self.get_read_mask(),
        )

    def get_read_mask(self) -> np.ndarray:
        """
        Determine read mask according to input area.

        This will generate a numpy array where pixel overlapping the input area
        are set True and thus will get filled by the read function. Pixel outside
        of the area are not considered for reading.

        On staged reading, i.e. first checking the product masks to assess valid
        pixels, this will avoid reading product bands in cases the product only covers
        pixels outside of the intended reading area.
        """
        area = self.area.buffer(self.area_pixelbuffer * self.tile.pixel_x_size)
        if area.is_empty:
            return np.zeros((self.tile.shape), dtype=bool)
        return geometry_mask(
            geometries=[mapping(area)],
            out_shape=self.tile.shape,
            transform=self.tile.transform,
            invert=True,
        )


class InputData(base.InputData):
    default_preprocessing_task: Callable = staticmethod(EOProduct.from_stac_item)
    driver_config_model: Type[BaseDriverConfig] = BaseDriverConfig
    params: BaseDriverConfig
    time: Optional[Union[TimeRange, List[TimeRange]]]
    area: BaseGeometry
    _products: Optional[IndexedFeatures] = None

    def __init__(
        self,
        input_params: dict,
        readonly: bool = False,
        input_key: Optional[str] = None,
        standalone: bool = False,
        **kwargs,
    ) -> None:
        """Initialize."""
        super().__init__(input_params, **kwargs)
        self.readonly = readonly
        self.input_key = input_key
        self.standalone = standalone

        self.params = self.driver_config_model(**input_params["abstract"])
        self.conf_dir = input_params.get("conf_dir")

        # we have to make sure, the cache path is absolute
        # not quite fond of this solution
        if self.params.cache:
            self.params.cache.path = MPath.from_inp(
                self.params.cache.dict()
            ).absolute_path(base_dir=input_params.get("conf_dir"))
        self.area = self._init_area(input_params)
        self.time = self.params.time

        self.eo_bands = [
            eo_band
            for source in self.params.source
            for eo_band in source.eo_bands(base_dir=self.conf_dir)
        ]

        if self.readonly:  # pragma: no cover
            return
        # don't use preprocessing tasks for Sentinel-2 products:
        if self.params.preprocessing_tasks or self.params.cache is not None:
            for item in self.source_items():
                self.add_preprocessing_task(
                    self.default_preprocessing_task,
                    fargs=(item,),
                    fkwargs=dict(cache_config=self.params.cache, cache_all=True),
                    key=item.id,
                    geometry=reproject_geometry(
                        item.geometry,
                        src_crs=mapchete_eo_settings.default_catalog_crs,
                        dst_crs=self.crs,
                    ),
                )
        else:
            logger.debug("do preprocessing tasks now rather than later")
            self._products = IndexedFeatures(
                [
                    self.default_preprocessing_task(
                        item, cache_config=self.params.cache, cache_all=True
                    )
                    for item in self.source_items()
                ]
            )

    def _init_area(self, input_params: dict) -> BaseGeometry:
        """Returns valid driver area for this process."""
        process_area = input_params["delimiters"]["effective_area"]
        if self.params.area:
            # read area parameter and intersect with effective area
            configured_area, configured_area_crs = guess_geometry(
                self.params.area,
                bounds=Bounds.from_inp(
                    input_params.get("delimiters", {}).get("effective_bounds"),
                    crs=getattr(input_params.get("pyramid"), "crs"),
                ),
                raise_if_empty=False,
            )
            process_area = process_area.intersection(
                reproject_geometry(
                    configured_area,
                    src_crs=configured_area_crs or self.crs,
                    dst_crs=self.crs,
                )
            )
        return process_area

    def source_items(self) -> Generator[Item, None, None]:
        already_returned = set()
        for source in self.params.source:
            area = reproject_geometry(
                self.area,
                src_crs=self.crs,
                dst_crs=source.catalog_crs,
            )
            if area.is_empty:
                continue
            for item in source.search(
                time=self.time,
                area=area,
                base_dir=self.conf_dir,
            ):
                # if item was already found in previous source, skip
                if item.id in already_returned:
                    continue

                # if item is new, add to list and yield
                already_returned.add(item.id)
                item.properties["mapchete_eo:source"] = source
                yield item
        logger.debug("returned set of %s items", len(already_returned))

    def bbox(self, out_crs: Optional[str] = None) -> BaseGeometry:
        """Return data bounding box."""
        return reproject_geometry(
            self.area,
            src_crs=self.pyramid.crs,
            dst_crs=self.pyramid.crs if out_crs is None else out_crs,
            segmentize_on_clip=True,
        )

    @cached_property
    def products(self) -> IndexedFeatures:
        """Hold preprocessed S2Products in an IndexedFeatures container."""

        # nothing to index here
        if self.readonly:
            return IndexedFeatures([])

        elif self._products is not None:
            return self._products

        # TODO: copied it from mapchete_satellite, not yet sure which use case this is
        elif self.standalone:  # pragma: no cover
            raise NotImplementedError()

        # if preprocessing tasks are ready, index them for further use
        elif self.preprocessing_tasks_results:
            return IndexedFeatures(
                [
                    self.get_preprocessing_task_result(item.id)
                    for item in self.source_items()
                    if not isinstance(item, CorruptedProductMetadata)
                ],
                crs=self.crs,
            )

        elif not self.preprocessing_tasks:
            return IndexedFeatures([])

        # this happens on task graph execution when preprocessing task results are not ready
        else:  # pragma: no cover
            raise PreprocessingNotFinished(
                f"products are not ready yet because {len(self.preprocessing_tasks)} preprocessing task(s) were not executed."
            )

    def open(self, tile, **kwargs) -> EODataCube:
        """
        Return InputTile object.
        """
        try:
            tile_products = self.products.filter(
                reproject_geometry(
                    tile.bbox,
                    src_crs=tile.crs,
                    dst_crs=mapchete_eo_settings.default_catalog_crs,
                ).bounds
            )
        except PreprocessingNotFinished:  # pragma: no cover
            tile_products = None
        return self.input_tile_cls(
            tile,
            products=tile_products,
            eo_bands=self.eo_bands,
            time=self.time,
            # passing on the input key is essential so dependent preprocessing tasks can be found!
            input_key=self.input_key,
            area=self.area.intersection(tile.bbox),
        )

    def cleanup(self):
        for product in self.products:
            product.clear_cached_data()
