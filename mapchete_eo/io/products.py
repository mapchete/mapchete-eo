import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Iterator, List, Optional

import numpy as np
import numpy.ma as ma
import xarray as xr
from mapchete.config import get_hash
from rasterio.enums import Resampling

from mapchete_eo.array.convert import to_dataarray, to_masked_array
from mapchete_eo.exceptions import (
    EmptySliceException,
    EmptyStackException,
    NoSourceProducts,
)
from mapchete_eo.io.items import get_item_property
from mapchete_eo.protocols import EOProductProtocol, GridProtocol
from mapchete_eo.sort import SortMethodConfig
from mapchete_eo.types import MergeMethod, NodataVals

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
            for s in generate_slices(
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
        for s in generate_slices(
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
    products: List[EOProductProtocol]
    datetime: datetime

    def __init__(
        self,
        name: Any,
        products: List[EOProductProtocol],
    ):
        self.name = name

        # a Slice can only be valid if it contains one or more products
        if products:
            self.products = products
        else:
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

    if sort:
        sort_dict = sort.model_dump()
        func = sort_dict.pop("func")
        slices = func(slices, **sort_dict)

    return slices


def merge_products(
    products: List[EOProductProtocol],
    merge_method: MergeMethod = MergeMethod.first,
    product_read_kwargs: dict = {},
    raise_empty: bool = True,
) -> ma.MaskedArray:
    """
    Merge given products into one array.
    """
    if len(products) == 0:
        raise NoSourceProducts("no products to merge")

    # we need to deactivate raising the EmptyProductException
    product_read_kwargs.update(raise_empty=False)

    # read first product
    out = products[0].read_np_array(**product_read_kwargs)

    # nothing to merge here
    if len(products) == 1:
        pass

    # fill in gaps sequentially, product by product
    elif merge_method == MergeMethod.first:
        for product in products[1:]:
            new = product.read_np_array(**product_read_kwargs)
            out[~out.mask] = new[~out.mask]
            out.mask[~out.mask] = new.mask[~out.mask]
            # if whole output array is filled, there is no point in reading more data
            if not out.mask.any():
                return out

    # read all and average
    elif merge_method == MergeMethod.average:
        out = (
            ma.stack(
                [
                    out,
                    *[
                        product.read_np_array(**product_read_kwargs)
                        for product in products[1:]
                    ],
                ]
            )
            .mean(axis=0)
            .astype(out.dtype, copy=False)
        )
    else:
        raise NotImplementedError(f"unknown merge method: {merge_method}")

    if raise_empty and out.mask.all():
        raise EmptySliceException(
            f"slice is empty after combining {len(products)} products"
        )

    return out


def generate_slices(
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
    for slice_ in slices:
        try:
            # if merge_products_by is none, each slice contains just one product
            # so nothing will have to be merged anyways
            yield to_dataarray(
                merge_products(
                    products=slice_.products,
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
                name=slice_.name,
                band_names=variables,
                attrs=slice_.properties,
            )
            # if at least one slice can be yielded, the stack is not empty
            stack_empty = False
        except EmptySliceException:
            pass

    if stack_empty:
        raise EmptyStackException("all slices are empty")
