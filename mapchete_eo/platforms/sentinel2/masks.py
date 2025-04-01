import logging
from typing import Generator, Iterator, List, Optional

import numpy as np
import numpy.ma as ma
import xarray as xr
from mapchete.protocols import GridProtocol
from mapchete.types import NodataVals

from mapchete_eo.array.convert import to_dataarray, to_masked_array
from mapchete_eo.exceptions import NoSourceProducts
from mapchete_eo.platforms.sentinel2.product import S2Product
from mapchete_eo.platforms.sentinel2.types import Resolution
from mapchete_eo.sort import SortMethodConfig
from mapchete_eo.types import MergeMethod
from mapchete_eo.exceptions import (
    AssetKeyError,
    CorruptedProduct,
    CorruptedSlice,
    EmptySliceException,
    EmptyStackException,
)


logger = logging.getLogger(__name__)


def read_masks(
    products: List[S2Product],
    grid: Optional[GridProtocol] = None,
    nodatavals: NodataVals = None,
    product_read_kwargs: dict = {},
) -> ma.MaskedArray:
    """Read grid window of Masks and merge into a 4D xarray."""
    return ma.stack(
        [
            to_masked_array(m)
            for m in generate_masks(
                products=products,
                grid=grid,
                nodatavals=nodatavals,
                product_read_kwargs=product_read_kwargs,
            )
        ]
    )


def masks_to_xarray(
    products: List[S2Product],
    grid: Optional[GridProtocol] = None,
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
        for s in generate_slice_masks_dataarrays(
            products=products,
            grid=grid,
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

    breakpoint()
    return xr.Dataset(
        data_vars={s.name: s for s in data_vars},
        coords=coords,
    ).transpose(slice_axis_name, band_axis_name, x_axis_name, y_axis_name)


def generate_masks(
    products: List[S2Product],
    grid: Optional[GridProtocol] = None,
    nodatavals: NodataVals = None,
    product_read_kwargs: dict = {},
) -> Iterator[xr.DataArray]:
    """
    Yield masks of slices or products into a cube to support advanced cube handling as Dataarrays.

    This should be analog to other read functions and can be used for read functions
    and read_levelled_cube as input if needed.

    TODO apply these masks on existing cubes (np_arrays, xarrays)
    """
    if len(products) == 0:
        raise NoSourceProducts("no products to read")

    logger.debug(f"reading {len(products)} product masks")

    if isinstance(nodatavals, list):
        nodataval = nodatavals[0]
    elif isinstance(nodatavals, float):
        nodataval = nodatavals
    else:
        nodataval = nodatavals

    product_read_kwargs = dict(
        product_read_kwargs,
    )
    for product_ in products:
        if grid is None:
            grid = product_.metadata.grid(Resolution["10m"])
        elif isinstance(grid, Resolution):
            grid = product_.metadata.grid(grid)
        mask_grid = product_.get_mask(
            grid=grid,
            mask_config=product_read_kwargs["mask_config"],
        )
        yield to_dataarray(
            ma.masked_where(mask_grid == 0, ma.expand_dims(mask_grid.data, axis=0)),
            nodataval=nodataval,
            name=product_.id,
            attrs=product_.item.properties,
        )


def merge_products_masks(
    products: List[S2Product],
    merge_method: MergeMethod = MergeMethod.first,
    product_read_kwargs: dict = {},
    raise_empty: bool = False,
) -> ma.MaskedArray:
    """
    Merge given products masks into one array.
    Should be analog to the merging of product slices with default 'first' method and 'all' method to use all available masks in datastripe/slice.
    """

    if merge_method == "average":
        raise ValueError(
            "Merge Method 'average' makes no sense for 'merge_products_masks' either 'first' or 'all'!"
        )

    def read_remaining_valid_products_masks(
        products_iter: Iterator[S2Product], product_read_kwargs: dict
    ) -> Generator[ma.MaskedArray, None, None]:
        """Yields and reads remaining products masks from iterator while discarding corrupt products."""
        try:
            for product in products_iter:
                try:
                    new = np.expand_dims(
                        product.get_mask(**product_read_kwargs).data, axis=0
                    )
                    yield ma.masked_array(data=new, mask=~new).astype(
                        np.bool_, copy=False
                    )
                except (AssetKeyError, CorruptedProduct) as exc:
                    logger.debug("skip product %s because of %s", product.item.id, exc)
        except StopIteration:
            return

    if len(products) == 0:  # pragma: no cover
        raise NoSourceProducts("no products to merge")

    products_iter = iter(products)

    # read first valid product
    for product in products_iter:
        try:
            out = np.expand_dims(
                product.get_mask(**product_read_kwargs).data, axis=0
            ).astype(np.bool_, copy=False)
            out = ma.masked_array(data=out, mask=~out)
            break
        except (AssetKeyError, CorruptedProduct) as exc:
            logger.debug("skip product mask %s because of %s", product.item.id, exc)
    else:
        # we cannot do anything here, as all products are broken
        raise CorruptedSlice("all products (masks) are broken here")

    # fill in gaps sequentially, product by product
    if merge_method == MergeMethod.first:
        for new in read_remaining_valid_products_masks(
            products_iter, product_read_kwargs
        ):
            out[~out.mask] = new[~out.mask].astype(np.bool_, copy=False)
            out.mask[~out.mask] = new.mask[~out.mask].astype(np.bool_, copy=False)
            # if whole output array is filled, there is no point in reading more data
            if out.mask.all():
                return out

    # read all and concatate
    elif merge_method == MergeMethod.all:

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
        out = ma.stack(
            list(
                _generate_arrays(
                    out,
                    read_remaining_valid_products_masks(
                        products_iter, product_read_kwargs
                    ),
                )
            ),
            dtype=np.bool_,
        ).any(axis=0)
    else:  # pragma: no cover
        raise NotImplementedError(f"unknown merge method: {merge_method}")

    if raise_empty and out.all():
        raise EmptySliceException(
            f"slice is empty after combining {len(products)} products"
        )

    return out


def generate_slice_masks_dataarrays(
    products: List[S2Product],
    grid: Optional[GridProtocol] = None,
    nodatavals: NodataVals = None,
    merge_products_by: Optional[str] = None,
    merge_method: MergeMethod = MergeMethod.first,
    sort: Optional[SortMethodConfig] = None,
    mask_name: List = ["EOxCloudless_masks"],
    product_read_kwargs: dict = {},
    raise_empty: bool = True,
) -> Iterator[xr.DataArray]:
    """
    Yield products or merged products into slices as DataArrays.
    """
    if len(products) == 0:
        raise NoSourceProducts("no products to read")

    stack_empty = True

    from mapchete_eo.io.products import products_to_slices

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
                    merge_products_masks(
                        products=slice.products,
                        merge_method=merge_method,
                        product_read_kwargs=dict(
                            product_read_kwargs,
                            grid=grid,
                        ),
                        raise_empty=raise_empty,
                    ),
                    nodataval=nodataval,
                    name=slice.name,
                    band_names=mask_name,
                    attrs=slice.properties,
                )
            # if at least one slice can be yielded, the stack is not empty
            stack_empty = False
        except (EmptySliceException, CorruptedSlice):
            pass

    if stack_empty:
        raise EmptyStackException("all slices are empty")
