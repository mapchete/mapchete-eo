import logging
from typing import Iterator, List, Optional, Union

import xarray as xr
from rasterio.enums import Resampling

from mapchete_eo.array.convert import masked_to_xarr_slice
from mapchete_eo.exceptions import (
    EmptyProductException,
    EmptySliceException,
    EmptyStackException,
    NoSourceProducts,
)
from mapchete_eo.io.products import group_products_per_property, merge_products
from mapchete_eo.protocols import EOProductProtocol, GridProtocol
from mapchete_eo.types import MergeMethod, NodataVals

logger = logging.getLogger(__name__)


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
