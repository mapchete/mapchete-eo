import logging
from dataclasses import dataclass
from typing import Any, Iterator, List, Optional, Union

import numpy.ma as ma
import pystac
from rasterio.enums import Resampling

from mapchete_eo.exceptions import (
    EmptyProductException,
    EmptySliceException,
    EmptyStackException,
    NoSourceProducts,
)
from mapchete_eo.io.mapchete_io_raster import read_raster
from mapchete_eo.io.path import absolute_asset_path
from mapchete_eo.io.products import group_products_per_property
from mapchete_eo.protocols import EOProductProtocol, GridProtocol
from mapchete_eo.types import BandLocation, MergeMethod, NodataVal, NodataVals

logger = logging.getLogger(__name__)


def asset_to_np_array(
    item: pystac.Item,
    asset: str,
    indexes: Union[List[int], int] = 1,
    grid: Union[GridProtocol, None] = None,
    resampling: Resampling = Resampling.nearest,
    nodataval: NodataVal = None,
) -> ma.MaskedArray:
    """
    Read grid window of STAC Items and merge into a 2D ma.MaskedArray.

    This is the main read method which is one way or the other being called from everywhere
    whenever a band is being read!
    """
    logger.debug("reading asset %s and indexes %s ...", asset, indexes)
    return read_raster(
        inp=absolute_asset_path(item, asset),
        indexes=indexes,
        grid=grid,
        resampling=resampling.name,
        dst_nodata=nodataval,
    ).data


def item_to_np_array(
    item: pystac.Item,
    band_locations: List[BandLocation],
    grid: Union[GridProtocol, None] = None,
    resampling: Resampling = Resampling.nearest,
    nodatavals: NodataVals = None,
    raise_empty: bool = False,
) -> ma.MaskedArray:
    """
    Read window of STAC Item and merge into a 3D ma.MaskedArray.
    """
    logger.debug("reading %s assets from item %s...", len(band_locations), item.id)
    out = ma.stack(
        [
            asset_to_np_array(
                item,
                band_location.asset_name,
                indexes=band_location.band_index,
                grid=grid,
                resampling=expanded_resampling,
                nodataval=nodataval,
            )
            for band_location, expanded_resampling, nodataval in zip(
                band_locations,
                expand_params(resampling, len(band_locations)),
                expand_params(nodatavals, len(band_locations)),
            )
        ]
    )

    if raise_empty and out.mask.all():
        raise EmptyProductException(
            f"all required assets of {item} over grid {grid} are empty."
        )

    return out


def products_to_np_array(
    products: List[EOProductProtocol],
    assets: Optional[List[str]] = None,
    eo_bands: Optional[List[str]] = None,
    grid: Union[GridProtocol, None] = None,
    resampling: Resampling = Resampling.nearest,
    nodatavals: NodataVals = None,
    merge_products_by: Union[str, None] = None,
    merge_method: MergeMethod = MergeMethod.first,
    product_read_kwargs: dict = {},
    raise_empty: bool = True,
) -> ma.MaskedArray:
    """Read grid window of EOProducts and merge into a 4D xarray."""

    if len(products) == 0:
        raise NoSourceProducts("no products to read")

    return ma.stack(
        [
            s.array
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


@dataclass
class Slice:
    """Class representing a merge of multiple products."""

    array: ma.MaskedArray
    # TODO: do we really want to store all of the products here?
    products: List[EOProductProtocol]
    merge_property: Optional[Any] = None


def generate_slices(
    products: List[EOProductProtocol],
    assets: Optional[List[str]] = None,
    eo_bands: Optional[List[str]] = None,
    grid: Union[GridProtocol, None] = None,
    resampling: Resampling = Resampling.nearest,
    nodatavals: NodataVals = None,
    merge_products_by: Union[str, None] = None,
    merge_method: MergeMethod = MergeMethod.first,
    product_read_kwargs: dict = {},
    raise_empty: bool = True,
) -> Iterator[Slice]:
    stack_empty = True

    # don't merge products
    if merge_products_by is None:
        logger.debug("reading %s products...", len(products))
        # Read products but skip empty ones if raise_empty is active.
        for product in products:
            try:
                yield Slice(
                    array=product.read_np_array(
                        assets=assets,
                        eo_bands=eo_bands,
                        grid=grid,
                        resampling=resampling,
                        nodatavals=nodatavals,
                        raise_empty=raise_empty,
                        **product_read_kwargs,
                    ),
                    products=[product],
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
                yield Slice(
                    array=merge_products(
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
                    products=products,
                    merge_property=merge_property,
                )
                stack_empty = False
            except EmptySliceException:
                pass

    if stack_empty:
        raise EmptyStackException("all slices are empty")


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


def expand_params(param, length):
    """
    Expand parameters if they are not a list.
    """
    if isinstance(param, list):
        if len(param) != length:
            raise ValueError(f"length of {param} must be {length} but is {len(param)}")
        return param
    return [param for _ in range(length)]
