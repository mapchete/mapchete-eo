from collections import defaultdict
from typing import Dict, List

import numpy.ma as ma

from mapchete_eo.exceptions import EmptySliceException, NoSourceProducts
from mapchete_eo.protocols import EOProductProtocol
from mapchete_eo.types import MergeMethod


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
