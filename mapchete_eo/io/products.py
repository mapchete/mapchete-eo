from __future__ import annotations

from contextlib import contextmanager
import logging
from collections import defaultdict
from datetime import datetime
import gc
from typing import Any, Dict, Generator, Iterator, List, Optional, Sequence

from mapchete import Timer
import numpy as np
import numpy.ma as ma
import xarray as xr
from mapchete.config import get_hash
from mapchete.geometry import to_shape
from mapchete.protocols import GridProtocol
from mapchete.types import NodataVals
from rasterio.enums import Resampling
from shapely.geometry import mapping
from shapely.ops import unary_union

from mapchete_eo.array.convert import to_dataarray, to_masked_array
from mapchete_eo.exceptions import (
    AssetKeyError,
    CorruptedProduct,
    CorruptedSlice,
    EmptySliceException,
    EmptyStackException,
    NoSourceProducts,
)
from mapchete_eo.io.items import get_item_property
from mapchete_eo.protocols import EOProductProtocol
from mapchete_eo.sort import SortMethodConfig
from mapchete_eo.types import MergeMethod


logger = logging.getLogger(__name__)


def products_to_np_array(
    products: List[EOProductProtocol],
    assets: Optional[List[str]] = None,
    eo_bands: Optional[List[str]] = None,
    grid: Optional[GridProtocol] = None,
    resampling: Resampling = Resampling.nearest,
    nodatavals: NodataVals = None,
    merge_products_by: Optional[str] = None,
    merge_method: MergeMethod = MergeMethod.first,
    sort: Optional[SortMethodConfig] = None,
    product_read_kwargs: dict = {},
    raise_empty: bool = True,
) -> ma.MaskedArray:
    """Read grid window of EOProducts and merge into a 4D xarray."""
    return ma.stack(
        [
            to_masked_array(s)
            for s in generate_slice_dataarrays(
                products=products,
                assets=assets,
                eo_bands=eo_bands,
                grid=grid,
                resampling=resampling,
                nodatavals=nodatavals,
                merge_products_by=merge_products_by,
                merge_method=merge_method,
                sort=sort,
                product_read_kwargs=product_read_kwargs,
                raise_empty=raise_empty,
            )
        ]
    )


def products_to_xarray(
    products: List[EOProductProtocol],
    assets: Optional[List[str]] = None,
    eo_bands: Optional[List[str]] = None,
    grid: Optional[GridProtocol] = None,
    resampling: Resampling = Resampling.nearest,
    nodatavals: NodataVals = None,
    slice_axis_name: str = "time",
    band_axis_name: str = "bands",
    x_axis_name: str = "x",
    y_axis_name: str = "y",
    merge_products_by: Optional[str] = None,
    merge_method: MergeMethod = MergeMethod.first,
    sort: Optional[SortMethodConfig] = None,
    raise_empty: bool = True,
    product_read_kwargs: dict = {},
) -> xr.Dataset:
    """Read grid window of EOProducts and merge into a 4D xarray."""
    data_vars = [
        s
        for s in generate_slice_dataarrays(
            products=products,
            assets=assets,
            eo_bands=eo_bands,
            grid=grid,
            resampling=resampling,
            nodatavals=nodatavals,
            merge_products_by=merge_products_by,
            merge_method=merge_method,
            sort=sort,
            product_read_kwargs=product_read_kwargs,
            raise_empty=raise_empty,
        )
    ]
    if merge_products_by and merge_products_by not in ["date", "datetime"]:
        coords = {merge_products_by: [s.name for s in data_vars]}
        slice_axis_name = merge_products_by
    else:
        coords = {
            slice_axis_name: list(
                np.array(
                    [product.item.datetime for product in products], dtype=np.datetime64
                )
            )
        }
    return xr.Dataset(
        data_vars={s.name: s for s in data_vars},
        coords=coords,
    ).transpose(slice_axis_name, band_axis_name, x_axis_name, y_axis_name)


class Slice:
    """Combine multiple products into one slice."""

    name: Any
    properties: dict
    products: Sequence[EOProductProtocol]
    datetime: datetime

    def __init__(
        self,
        name: Any,
        products: Sequence[EOProductProtocol],
    ):
        self.name = name

        # a Slice can only be valid if it contains one or more products
        if products:
            self.products = products
        else:  # pragma: no cover
            raise ValueError("at least one product must be provided.")

        # calculate mean datetime
        timestamps = [
            product.item.datetime.timestamp()
            for product in self.products
            if product.item.datetime
        ]
        mean_timestamp = sum(timestamps) / len(timestamps)
        self.datetime = datetime.fromtimestamp(mean_timestamp)

        # generate combined properties
        self.properties = {}
        for key in self.products[0].item.properties.keys():
            try:
                self.properties[key] = self.get_property(key)
            except ValueError:
                self.properties[key] = None

    def __repr__(self) -> str:
        return f"<Slice {self.name} ({len(self.products)} products)>"

    @property
    def __geom_interface__(self) -> Dict:
        if self.products:
            return mapping(
                unary_union([to_shape(product) for product in self.products])
            )

        raise EmptySliceException

    @contextmanager
    def cached(self) -> Generator[Slice, None, None]:
        """Clear caches and run garbage collector when context manager is closed."""
        yield self
        with Timer() as tt:
            self.clear_cached_data()
            gc.collect()
        logger.debug("Slice cache cleared and garbage collected in %s", tt)

    def clear_cached_data(self):
        logger.debug("clear caches of all products in slice")
        for product in self.products:
            product.clear_cached_data()

    def get_property(self, property: str) -> Any:
        """
        Return merged property over all products.

        If property values are the same over all products, it will be returned. Otherwise a
        ValueError is raised.
        """
        # if set of value hashes has a length of 1, all values are the same
        values = [
            get_hash(get_item_property(product.item, property=property))
            for product in self.products
        ]
        if len(set(values)) == 1:
            return get_item_property(self.products[0].item, property=property)

        raise ValueError(
            f"cannot get unique property {property} from products {self.products}"
        )

    def read(
        self,
        merge_method: MergeMethod = MergeMethod.first,
        product_read_kwargs: dict = {},
        raise_empty: bool = True,
    ) -> ma.MaskedArray:
        logger.debug("Slice: read from %s products", len(self.products))
        return merge_products(
            products=self.products,
            merge_method=merge_method,
            product_read_kwargs=product_read_kwargs,
            raise_empty=raise_empty,
        )


def products_to_slices(
    products: List[EOProductProtocol],
    group_by_property: Optional[str] = None,
    sort: Optional[SortMethodConfig] = None,
) -> List[Slice]:
    """Group products per given property into Slice objects and optionally sort slices."""
    if group_by_property:
        grouped = defaultdict(list)
        for product in products:
            grouped[product.get_property(group_by_property)].append(product)
        slices = [Slice(key, products) for key, products in grouped.items()]
    else:
        slices = [Slice(product.item.id, [product]) for product in products]

    # also check if slices is even a list, otherwise it will raise an error
    if sort and slices:
        sort_dict = sort.model_dump()
        func = sort_dict.pop("func")
        slices = func(slices, **sort_dict)

    return slices


def merge_products(
    products: Sequence[EOProductProtocol],
    merge_method: MergeMethod = MergeMethod.first,
    product_read_kwargs: dict = {},
    raise_empty: bool = True,
) -> ma.MaskedArray:
    """
    Merge given products into one array.
    """

    def read_remaining_valid_products(
        products_iter: Iterator[EOProductProtocol], product_read_kwargs: dict
    ) -> Generator[ma.MaskedArray, None, None]:
        """Yields and reads remaining products from iterator while discarding corrupt products."""
        try:
            for product in products_iter:
                try:
                    yield product.read_np_array(**product_read_kwargs)
                except (AssetKeyError, CorruptedProduct) as exc:
                    logger.debug("skip product %s because of %s", product.item.id, exc)
        except StopIteration:
            return

    if len(products) == 0:  # pragma: no cover
        raise NoSourceProducts("no products to merge")

    # we need to deactivate raising the EmptyProductException
    product_read_kwargs.update(raise_empty=False)

    products_iter = iter(products)

    # read first valid product
    for product in products_iter:
        try:
            out = product.read_np_array(**product_read_kwargs)
            break
        except (AssetKeyError, CorruptedProduct) as exc:
            logger.debug("skip product %s because of %s", product.item.id, exc)
    else:
        # we cannot do anything here, as all products are broken
        raise CorruptedSlice("all products are broken here")

    # fill in gaps sequentially, product by product
    if merge_method == MergeMethod.first:
        for new in read_remaining_valid_products(products_iter, product_read_kwargs):
            masked = out.mask
            # Update values at masked locations
            out[masked] = new[masked]
            # Update mask at masked locations (e.g., unmask them)
            out.mask[masked] = new.mask[masked]
            # if whole output array is filled, there is no point in reading more data
            if not out.mask.any():
                return out

    # read all and average
    elif merge_method == MergeMethod.average:

        def _generate_arrays(
            first_product_array: ma.MaskedArray,
            remaining_product_arrays: Generator[ma.MaskedArray, None, None],
        ) -> Generator[ma.MaskedArray, None, None]:
            """Yield all available product arrays."""
            yield first_product_array
            yield from remaining_product_arrays

        # explicitly specify dtype to avoid casting of integer arrays to floats
        # during mean conversion:
        # https://numpy.org/doc/stable/reference/generated/numpy.mean.html#numpy.mean
        arrays = list(
            _generate_arrays(
                out,
                read_remaining_valid_products(products_iter, product_read_kwargs),
            )
        )

        # Filter out arrays that are entirely masked
        valid_arrays = [a for a in arrays if not ma.getmaskarray(a).all()]

        if valid_arrays:
            stacked = ma.stack(valid_arrays, dtype=out.dtype)
            out = stacked.mean(axis=0, dtype=out.dtype)
        else:
            # All arrays were fully masked — return fully masked output
            out = ma.masked_all(out.shape, dtype=out.dtype)

    else:  # pragma: no cover
        raise NotImplementedError(f"unknown merge method: {merge_method}")

    if raise_empty and out.mask.all():
        raise EmptySliceException(
            f"slice is empty after combining {len(products)} products"
        )

    return out


def generate_slice_dataarrays(
    products: List[EOProductProtocol],
    assets: Optional[List[str]] = None,
    eo_bands: Optional[List[str]] = None,
    grid: Optional[GridProtocol] = None,
    resampling: Resampling = Resampling.nearest,
    nodatavals: NodataVals = None,
    merge_products_by: Optional[str] = None,
    merge_method: MergeMethod = MergeMethod.first,
    sort: Optional[SortMethodConfig] = None,
    product_read_kwargs: dict = {},
    raise_empty: bool = True,
) -> Iterator[xr.DataArray]:
    """
    Yield products or merged products into slices as DataArrays.
    """
    if len(products) == 0:
        raise NoSourceProducts("no products to read")

    stack_empty = True
    assets = assets or []
    eo_bands = eo_bands or []
    variables = assets or eo_bands

    # group products into slices and sort slices if configured
    slices = products_to_slices(
        products, group_by_property=merge_products_by, sort=sort
    )

    logger.debug(
        "reading %s products in %s groups...",
        len(products),
        len(slices),
    )
    if isinstance(nodatavals, list):
        nodataval = nodatavals[0]
    elif isinstance(nodatavals, float):
        nodataval = nodatavals
    else:
        nodataval = nodatavals
    for slice in slices:
        try:
            # if merge_products_by is none, each slice contains just one product
            # so nothing will have to be merged anyways
            with slice.cached():
                yield to_dataarray(
                    merge_products(
                        products=slice.products,
                        merge_method=merge_method,
                        product_read_kwargs=dict(
                            product_read_kwargs,
                            assets=assets,
                            eo_bands=eo_bands,
                            grid=grid,
                            resampling=resampling,
                            nodatavals=nodatavals,
                            raise_empty=raise_empty,
                        ),
                        raise_empty=raise_empty,
                    ),
                    nodataval=nodataval,
                    name=slice.name,
                    band_names=variables,
                    attrs=slice.properties,
                )
            # if at least one slice can be yielded, the stack is not empty
            stack_empty = False
        except (EmptySliceException, CorruptedSlice):
            pass

    if stack_empty:
        raise EmptyStackException("all slices are empty")
