from __future__ import annotations

import datetime
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
from mapchete_eo.io import products_to_xarray
from mapchete_eo.product import EOProduct
from mapchete_eo.protocols import EOProductProtocol
from mapchete_eo.search.stac_static import STACStaticCatalog
from mapchete_eo.settings import DEFAULT_CATALOG_CRS
from mapchete_eo.time import to_datetime
from mapchete_eo.types import MergeMethod, NodataVal, NodataVals


class BaseDriverConfig(BaseModel):
    format: str
    start_time: Union[datetime.date, datetime.datetime]
    end_time: Union[datetime.date, datetime.datetime]
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
    products: List[EOProductProtocol]
    eo_bands: dict
    start_time: Union[datetime.datetime, datetime.date]
    end_time: Union[datetime.datetime, datetime.date]

    def __init__(
        self,
        tile: BufferedTile,
        products: List[EOProductProtocol],
        eo_bands: dict,
        start_time: Union[datetime.datetime, datetime.date],
        end_time: Union[datetime.datetime, datetime.date],
        **kwargs,
    ) -> None:
        """Initialize."""
        self.tile = tile
        self.products = products
        self.eo_bands = eo_bands
        self.start_time = start_time
        self.end_time = end_time

    def read(
        self,
        assets: List[str] = [],
        eo_bands: List[str] = [],
        start_time: Union[str, datetime.datetime, None] = None,
        end_time: Union[str, datetime.datetime, None] = None,
        timestamps: Union[List[Union[str, datetime.datetime]], None] = None,
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
            tile=self.tile,
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
        start_time: Union[str, datetime.datetime, None] = None,
        end_time: Union[str, datetime.datetime, None] = None,
        timestamps: Union[List[Union[str, datetime.datetime]], None] = None,
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

    def _get_assets(self, indexes: Union[int, str, List[Union[int, str]], None] = None):
        if indexes is None:
            return list(range(len(self.eo_bands)))
        out = []
        for idx in indexes if isinstance(indexes, list) else [indexes]:
            if isinstance(idx, str):
                for band in self.eo_bands:
                    if idx == band.get("name"):
                        out.append(band.get("name"))
                        break
                else:
                    raise ValueError(f"cannot find eo:band asset name {idx}")
            elif isinstance(idx, int):
                out.append(self.eo_bands[idx - 1].get("name"))
            else:
                raise TypeError(
                    f"band index must either be an integer or a string: {idx}"
                )
        return out


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
        self.start_time = self.params.start_time
        self.end_time = self.params.end_time

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
                self.start_time, self.end_time, self._bounds
            )

        if not self.readonly:
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
