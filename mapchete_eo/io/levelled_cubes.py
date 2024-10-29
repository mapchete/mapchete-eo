import logging
from typing import List, Optional

import numpy as np
import numpy.ma as ma
import xarray as xr
from mapchete.protocols import GridProtocol
from mapchete.types import NodataVals
from rasterio.enums import Resampling

from mapchete_eo.array.convert import to_dataset
from mapchete_eo.exceptions import (
    CorruptedSlice,
    EmptySliceException,
    EmptyStackException,
)
from mapchete_eo.io.products import products_to_slices
from mapchete_eo.protocols import EOProductProtocol
from mapchete_eo.sort import SortMethodConfig, TargetDateSort
from mapchete_eo.types import MergeMethod

logger = logging.getLogger(__name__)


def read_levelled_cube_to_np_array(
    products: List[EOProductProtocol],
    target_height: int,
    assets: Optional[List[str]] = None,
    eo_bands: Optional[List[str]] = None,
    grid: Optional[GridProtocol] = None,
    resampling: Resampling = Resampling.nearest,
    nodatavals: NodataVals = None,
    merge_products_by: Optional[str] = None,
    merge_method: MergeMethod = MergeMethod.first,
    sort: SortMethodConfig = TargetDateSort(),
    product_read_kwargs: dict = {},
    raise_empty: bool = True,
) -> ma.MaskedArray:
    """
    Read products as slices into a cube by filling up nodata gaps with next slice.
    """

    slices = products_to_slices(
        products=products, group_by_property=merge_products_by, sort=sort
    )
    logger.debug(
        "generating levelled cube with height %s from %s slices",
        target_height,
        len(slices),
    )
    out = None

    # pick slices one by one
    for slice_ in slices:
        # first iteration
        if out is None:
            try:
                first_slice_array = slice_.read(
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
                )
            except (EmptySliceException, CorruptedSlice):
                continue
            shape = (target_height, *first_slice_array.shape)
            out = ma.masked_array(
                data=np.zeros(shape, dtype=first_slice_array.dtype),
                mask=np.ones(shape, dtype=first_slice_array.mask.dtype),
                fill_value=first_slice_array.fill_value,
            )
            # insert first slice to output cube
            logger.debug("inserting first slice into cube ...")
            out[0] = first_slice_array

        else:
            # generate mask of holes to be filled in output cube
            cube_nodata_mask = out.mask.sum(axis=0, dtype=bool).sum(axis=0, dtype=bool)
            logger.debug(
                "find a product with %s unmasked pixels to fill", cube_nodata_mask.sum()
            )
            try:
                slice_array = slice_.read(
                    merge_method=merge_method,
                    product_read_kwargs=dict(
                        product_read_kwargs,
                        assets=assets,
                        eo_bands=eo_bands,
                        grid=grid,
                        resampling=resampling,
                        nodatavals=nodatavals,
                        raise_empty=raise_empty,
                        target_nodata_mask=cube_nodata_mask,
                    ),
                )
            except (EmptySliceException, CorruptedSlice) as exc:
                logger.debug("skip slice %s: %s", slice_, str(exc))
                continue

            # iterate through layers of cube
            for layer_index in range(target_height):
                # go to next layer if layer is full
                if not out[layer_index].mask.any():
                    logger.debug("cube layer %s full, jump to next", layer_index)
                    continue

                # determine empty patches of current layer
                empty_patches = out[layer_index].mask.copy()
                logger.debug(
                    "slice has %s masked pixels", slice_array[empty_patches].mask.sum()
                )

                logger.debug(
                    "layer %s has %s masked pixels",
                    layer_index,
                    out[layer_index].mask.sum(),
                )
                logger.debug("fill ...")
                # insert slice data into empty patches of layer
                out[layer_index][empty_patches] = slice_array[empty_patches]
                logger.debug(
                    "layer %s has %s masked pixels",
                    layer_index,
                    out[layer_index].mask.sum(),
                )

                # remove slice values which were just inserted for next layer
                slice_array[empty_patches] = ma.masked
                if slice_array.mask.all():
                    logger.debug("slice fully inserted into cube, skipping")
                    break

        # all filled up? let's get outta here!
        if not out.mask.any():
            break

    if out is None:
        raise EmptyStackException("all slices in stack are empty or corrupt")

    return out


def read_levelled_cube_to_xarray(
    products: List[EOProductProtocol],
    target_height: int,
    assets: Optional[List[str]] = None,
    eo_bands: Optional[List[str]] = None,
    grid: Optional[GridProtocol] = None,
    resampling: Resampling = Resampling.nearest,
    nodatavals: NodataVals = None,
    merge_products_by: Optional[str] = None,
    merge_method: MergeMethod = MergeMethod.first,
    sort: SortMethodConfig = TargetDateSort(),
    product_read_kwargs: dict = {},
    raise_empty: bool = True,
    slice_axis_name: str = "layers",
    band_axis_name: str = "bands",
    x_axis_name: str = "x",
    y_axis_name: str = "y",
) -> xr.Dataset:
    """
    Read products as slices into a cube by filling up nodata gaps with next slice.
    """
    assets = assets or []
    eo_bands = eo_bands or []
    variables = assets or eo_bands
    return to_dataset(
        read_levelled_cube_to_np_array(
            products=products,
            target_height=target_height,
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
        ),
        slice_names=[f"layer-{ii}" for ii in range(target_height)],
        band_names=variables,
        slice_axis_name=slice_axis_name,
        band_axis_name=band_axis_name,
        x_axis_name=x_axis_name,
        y_axis_name=y_axis_name,
    )
