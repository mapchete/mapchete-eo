import logging
from typing import Iterator, List, Optional, Union

import numpy.ma as ma
import pystac
import xarray as xr
from rasterio.enums import Resampling

from mapchete_eo.array.convert import masked_to_xarr_slice, xarr_to_masked
from mapchete_eo.exceptions import (
    EmptyProductException,
    EmptySliceException,
    EmptyStackException,
    NoSourceProducts,
)
from mapchete_eo.io.mapchete_io_raster import read_raster
from mapchete_eo.io.path import absolute_asset_path
from mapchete_eo.io.products import group_products_per_property, merge_products
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
    return ma.stack(
        [
            xarr_to_masked(s)
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
) -> Iterator[xr.DataArray]:
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
                yield masked_to_xarr_slice(
                    product.read_np_array(
                        assets=assets,
                        eo_bands=eo_bands,
                        grid=grid,
                        resampling=resampling,
                        nodatavals=nodatavals,
                        raise_empty=raise_empty,
                        **product_read_kwargs,
                    ),
                    product.item.id,
                    band_names=variables,
                    slice_attrs=product.item.properties,
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
                yield masked_to_xarr_slice(
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
                    merge_property,
                    band_names=variables,
                )
                stack_empty = False
            except EmptySliceException:
                pass

    if stack_empty:
        raise EmptyStackException("all slices are empty")


def expand_params(param, length):
    """
    Expand parameters if they are not a list.
    """
    if isinstance(param, list):
        if len(param) != length:
            raise ValueError(f"length of {param} must be {length} but is {len(param)}")
        return param
    return [param for _ in range(length)]
