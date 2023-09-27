import logging
from typing import List, Union

import numpy.ma as ma
import pystac
from rasterio.enums import Resampling

from mapchete_eo.io.assets import eo_bands_to_assets_indexes
from mapchete_eo.io.mapchete_io_raster import read_raster
from mapchete_eo.io.path import absolute_asset_path
from mapchete_eo.io.products import group_products_per_property
from mapchete_eo.protocols import EOProductProtocol, GridProtocol
from mapchete_eo.types import MergeMethod, NodataVal, NodataVals

logger = logging.getLogger(__name__)


def products_to_np_array(
    products: List[EOProductProtocol] = [],
    assets: List[str] = [],
    eo_bands: List[str] = [],
    grid: Union[GridProtocol, None] = None,
    resampling: Resampling = Resampling.nearest,
    nodatavals: NodataVals = None,
    merge_products_by: Union[str, None] = None,
    merge_method: MergeMethod = MergeMethod.first,
    product_read_kwargs: dict = {},
) -> ma.MaskedArray:
    """Read grid window of EOProducts and merge into a 4D xarray."""

    if len(products) == 0:
        raise ValueError("no products to read")

    # don't merge products
    if merge_products_by is None:
        logger.debug("reading %s products...", len(products))
        return ma.stack(
            [
                product.read_np_array(
                    assets=assets,
                    eo_bands=eo_bands,
                    grid=grid,
                    resampling=resampling,
                    nodatavals=nodatavals,
                    **product_read_kwargs,
                )
                for product in products
            ]
        )

    # merge products
    else:
        products_per_property = group_products_per_property(products, merge_products_by)
        logger.debug(
            "reading %s products in %s groups...",
            len(products),
            len(products_per_property),
        )
        return ma.stack(
            [
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
                    ),
                )
                for products in products_per_property.values()
            ]
        )


def merge_products(
    products: List[EOProductProtocol] = [],
    merge_method: MergeMethod = MergeMethod.first,
    product_read_kwargs: dict = {},
) -> ma.MaskedArray:
    """
    Merge given products into one array.
    """
    if len(products) == 0:
        raise ValueError("no products to merge")

    # read first product
    out = products[0].read_np_array(**product_read_kwargs)

    # nothing to merge here
    if len(products) == 1:
        return out

    # fill in gaps sequentially, product by product
    elif merge_method == MergeMethod.first:
        for product in products[1:]:
            new = product.read_np_array(**product_read_kwargs)
            out[~out.mask] = new[~out.mask]
            out.mask[~out.mask] = new.mask[~out.mask]
            # if whole output array is filled, there is no point in reading more data
            if not out.mask.any():
                return out
        return out

    # read all and average
    elif merge_method == MergeMethod.average:
        return (
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

    raise NotImplementedError(f"unknown merge method: {merge_method}")


def expand_params(param, length):
    """
    Expand parameters if they are not a list.
    """
    if isinstance(param, list):
        if len(param) != length:
            raise ValueError(f"length of {param} must be {length} but is {len(param)}")
        return param
    return [param for _ in range(length)]


def item_to_np_array(
    item: pystac.Item,
    eo_bands: List[str] = [],
    assets: List[str] = [],
    grid: Union[GridProtocol, None] = None,
    resampling: Resampling = Resampling.nearest,
    nodatavals: NodataVals = None,
    fill_value: int = 0,
) -> ma.MaskedArray:
    """
    Read window of STAC Item and merge into a 3D ma.MaskedArray.
    """
    if (len(eo_bands) and len(assets)) or (not len(eo_bands) and not len(assets)):
        raise ValueError("either assets or eo_bands have to be provided")
    # determine array location either by assets or eo_bands
    assets_indexes = (
        eo_bands_to_assets_indexes(item, eo_bands)
        if eo_bands
        else [(asset, 1) for asset in assets]
    )
    logger.debug("reading %s assets from item %s...", len(assets_indexes), item.id)
    return ma.stack(
        [
            asset_to_np_array(
                item,
                asset,
                indexes=index,
                grid=grid,
                resampling=expanded_resampling,
                nodataval=nodataval,
            )
            for (asset, index), expanded_resampling, nodataval in zip(
                assets_indexes,
                expand_params(resampling, len(assets_indexes)),
                expand_params(nodatavals, len(assets_indexes)),
            )
        ]
    )


def asset_to_np_array(
    item: pystac.Item,
    asset: str,
    indexes: Union[list, int] = 1,
    grid: Union[GridProtocol, None] = None,
    resampling: Resampling = Resampling.nearest,
    nodataval: NodataVal = None,
) -> ma.MaskedArray:
    """
    Read grid window of STAC Items and merge into a 2D ma.MaskedArray.
    """
    logger.debug("reading asset %s and indexes %s ...", asset, indexes)
    return read_raster(
        inp=absolute_asset_path(item, asset),
        indexes=indexes,
        grid=grid,
        resampling=resampling.name,
        dst_nodata=nodataval,
    ).data
