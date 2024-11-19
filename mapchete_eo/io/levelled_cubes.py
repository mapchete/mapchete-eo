import logging
from typing import List, Optional

import numpy as np
import numpy.ma as ma
from numpy.typing import DTypeLike
import xarray as xr
from mapchete.pretty import pretty_bytes
from mapchete.protocols import GridProtocol
from mapchete.types import NodataVals, NodataVal
from rasterio.enums import Resampling

from mapchete_eo.array.convert import to_dataset
from mapchete_eo.exceptions import (
    CorruptedSlice,
    EmptySliceException,
    EmptyStackException,
    NoSourceProducts,
)
from mapchete_eo.io.products import products_to_slices
from mapchete_eo.protocols import EOProductProtocol
from mapchete_eo.sort import SortMethodConfig, TargetDateSort
from mapchete_eo.types import MergeMethod

logger = logging.getLogger(__name__)


def read_levelled_cube_to_np_array(
    products: List[EOProductProtocol],
    target_height: int,
    grid: GridProtocol,
    assets: Optional[List[str]] = None,
    eo_bands: Optional[List[str]] = None,
    resampling: Resampling = Resampling.nearest,
    nodatavals: NodataVals = None,
    merge_products_by: Optional[str] = None,
    merge_method: MergeMethod = MergeMethod.first,
    sort: SortMethodConfig = TargetDateSort(),
    product_read_kwargs: dict = {},
    raise_empty: bool = True,
    out_dtype: DTypeLike = np.uint16,
    out_fill_value: NodataVal = 0,
) -> ma.MaskedArray:
    """
    Read products as slices into a cube by filling up nodata gaps with next slice.
    """
    if len(products) == 0:
        raise NoSourceProducts("no products to read")

    bands = assets or eo_bands
    if bands is None:
        raise ValueError("either assets or eo_bands have to be set")

    out_shape = (target_height, len(bands), *grid.shape)
    out: ma.MaskedArray = ma.masked_array(
        data=np.zeros(out_shape, dtype=out_dtype),
        mask=np.ones(out_shape, dtype=out_dtype),
        fill_value=out_fill_value,
    )
    logger.debug(
        "empty cube with shape %s has %s",
        out.shape,
        pretty_bytes(out.size * out.itemsize),
    )

    logger.debug("sort products into slices ...")
    slices = products_to_slices(
        products=products, group_by_property=merge_products_by, sort=sort
    )
    logger.debug(
        "generating levelled cube with height %s from %s slices",
        target_height,
        len(slices),
    )

    slices_read_count, slices_skip_count = 0, 0

    # pick slices one by one
    for slice_count, slice in enumerate(slices, 1):
        # all filled up? let's get outta here!
        if not out.mask.any():
            logger.debug("cube is full, quitting!")
            break

        # generate 2D mask of holes to be filled in output cube
        cube_nodata_mask = out.mask.any(axis=0).any(axis=0)

        # read slice
        try:
            logger.debug(
                "see if slice %s %s has some of the %s unmasked pixels for cube",
                slice_count,
                slice,
                cube_nodata_mask.sum(),
            )
            with slice.cached():
                slice_array = slice.read(
                    merge_method=merge_method,
                    product_read_kwargs=dict(
                        product_read_kwargs,
                        assets=assets,
                        eo_bands=eo_bands,
                        grid=grid,
                        resampling=resampling,
                        nodatavals=nodatavals,
                        raise_empty=raise_empty,
                        target_mask=~cube_nodata_mask.copy(),
                    ),
                )
            slices_read_count += 1
        except (EmptySliceException, CorruptedSlice) as exc:
            logger.debug("skipped slice %s: %s", slice, str(exc))
            slices_skip_count += 1
            continue

        # if slice was not empty, fill pixels into cube
        logger.debug("add slice %s array to cube", slice)

        # iterate through layers of cube
        for layer_index in range(target_height):
            # go to next layer if layer is full
            if not out[layer_index].mask.any():
                logger.debug("layer %s: full, jump to next", layer_index)
                continue

            # determine empty patches of current layer
            empty_patches = out[layer_index].mask.copy()
            pixels_for_layer = (~slice_array[empty_patches].mask).sum()

            # when slice has nothing to offer for this layer, skip
            if pixels_for_layer == 0:
                logger.debug(
                    "layer %s: slice has no pixels for this layer, jump to next",
                    layer_index,
                )
                continue

            logger.debug(
                "layer %s: fill with %s pixels ...",
                layer_index,
                pixels_for_layer,
            )
            # insert slice data into empty patches of layer
            out[layer_index][empty_patches] = slice_array[empty_patches]
            masked_pixels = out[layer_index].mask.sum()
            total_pixels = out[layer_index].size
            percent_full = round(
                100 * ((total_pixels - masked_pixels) / total_pixels), 2
            )
            logger.debug(
                "layer %s: %s%% filled (%s empty pixels remaining)",
                layer_index,
                percent_full,
                out[layer_index].mask.sum(),
            )

            # remove slice values which were just inserted for next layer
            slice_array[empty_patches] = ma.masked

            if slice_array.mask.all():
                logger.debug("slice fully inserted into cube, skipping")
                break

        masked_pixels = out.mask.sum()
        total_pixels = out.size
        percent_full = round(100 * ((total_pixels - masked_pixels) / total_pixels), 2)
        logger.debug(
            "cube is %s%% filled (%s empty pixels remaining)",
            percent_full,
            masked_pixels,
        )

    logger.debug(
        "%s slices read, %s slices skipped", slices_read_count, slices_skip_count
    )

    if raise_empty and out.mask.all():
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
