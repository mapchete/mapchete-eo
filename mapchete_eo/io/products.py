import logging
from collections import defaultdict
from typing import Dict, Iterator, List, Optional

import numpy as np
import numpy.ma as ma
import xarray as xr
from rasterio.enums import Resampling

from mapchete_eo.array.convert import to_dataarray, to_masked_array
from mapchete_eo.exceptions import (
    EmptyProductException,
    EmptySliceException,
    EmptyStackException,
    NoSourceProducts,
)
from mapchete_eo.protocols import EOProductProtocol, GridProtocol
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


def group_products_per_property(
    products: List[EOProductProtocol], property: str
) -> Dict:
    """Group products per given property."""
    out = defaultdict(list)
    for product in products:
        out[product.get_property(property)].append(product)
    return out


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

    # don't merge products
    if merge_products_by is None:
        logger.debug("reading %s products...", len(products))
        # Read products but skip empty ones if raise_empty is active.
        for product in products:
            try:
                yield to_dataarray(
                    product.read_np_array(
                        assets=assets,
                        eo_bands=eo_bands,
                        grid=grid,
                        resampling=resampling,
                        nodatavals=nodatavals,
                        raise_empty=raise_empty,
                        **product_read_kwargs,
                    ),
                    name=product.item.id,
                    band_names=variables,
                    attrs=product.item.properties,
                )
                stack_empty = False
            except EmptyProductException:
                pass

    # merge products
    else:
        products_per_property = group_products_per_property(products, merge_products_by)
        logger.debug(
            "reading %s products in %s groups...",
            len(products),
            len(products_per_property),
        )
        for merge_property, products in products_per_property.items():
            try:
                yield to_dataarray(
                    merge_products(
                        products=products,
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
                    name=merge_property,
                    band_names=variables,
                )
                stack_empty = False
            except EmptySliceException:
                pass

    if stack_empty:
        raise EmptyStackException("all slices are empty")
