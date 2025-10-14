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
    read_mask: Optional[np.ndarray] = None,
) -> ma.MaskedArray:
    """
    Read products as slices into a cube by filling up nodata gaps with next slice.

    If a read_mask is provided, only the pixels marked True are considered to be read.
    """
    if len(products) == 0:  # pragma: no cover
        raise NoSourceProducts("no products to read")
    bands = assets or eo_bands
    if bands is None:  # pragma: no cover
        raise ValueError("either assets or eo_bands have to be set")
    out_shape = (target_height, len(bands), *grid.shape)

    # 2D read_mask shape
    if read_mask is None:
        read_mask = np.ones(grid.shape, dtype=bool)
    elif read_mask.ndim != 2:  # pragma: no cover
        raise ValueError(
            "read_mask must be 2-dimensional, not %s-dimensional",
            read_mask.ndim,
        )
    out: ma.MaskedArray = ma.masked_array(
        data=np.full(out_shape, out_fill_value, dtype=out_dtype),
        mask=np.ones(out_shape, dtype=bool),
        fill_value=out_fill_value,
    )

    if not read_mask.any():
        logger.debug("nothing to read")
        return out

    # extrude mask to match each layer
    layer_read_mask = np.stack([read_mask for _ in bands])

    def _cube_read_mask() -> np.ndarray:
        # This is only needed for debug output, thus there is no need to materialize always
        return np.stack([layer_read_mask for _ in range(target_height)])

    logger.debug(
        "empty cube with shape %s has %s and %s pixels to be filled",
        out.shape,
        pretty_bytes(out.size * out.itemsize),
        _cube_read_mask().sum(),
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
    for slice_count, slice_ in enumerate(slices, 1):
        # all filled up? let's get outta here!
        if not out.mask.any():
            logger.debug("cube has no pixels to be filled, quitting!")
            break

        # generate 2D mask of holes to be filled in output cube
        cube_nodata_mask = np.logical_and(out.mask.any(axis=0).any(axis=0), read_mask)

        # read slice
        try:
            logger.debug(
                "see if slice %s %s has some of the %s unmasked pixels for cube",
                slice_count,
                slice_,
                cube_nodata_mask.sum(),
            )
            with slice_.cached():
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
                        read_mask=cube_nodata_mask.copy(),
                        out_dtype=out_dtype,
                    ),
                )
            slices_read_count += 1
        except (EmptySliceException, CorruptedSlice) as exc:
            logger.debug("skipped slice %s: %s", slice_, str(exc))
            slices_skip_count += 1
            continue

        # if slice was not empty, fill pixels into cube
        logger.debug("add slice %s array to cube", slice_)

        # iterate through layers of cube
        for layer_index in range(target_height):
            # go to next layer if layer is full
            if not out[layer_index].mask.any():
                logger.debug("layer %s: full, jump to next", layer_index)
                continue

            # determine empty patches of current layer
            empty_patches = np.logical_and(out[layer_index].mask, layer_read_mask)
            remaining_pixels_for_layer = (~slice_array[empty_patches].mask).sum()

            # when slice has nothing to offer for this layer, skip
            if remaining_pixels_for_layer == 0:
                logger.debug(
                    "layer %s: slice has no pixels for this layer, jump to next",
                    layer_index,
                )
                continue

            # insert slice data into empty patches of layer
            logger.debug(
                "layer %s: fill with %s pixels ...",
                layer_index,
                remaining_pixels_for_layer,
            )
            out[layer_index][empty_patches] = slice_array[empty_patches]

            # report on layer fill status
            logger.debug(
                "layer %s: %s",
                layer_index,
                _percent_full(
                    remaining=np.logical_and(
                        out[layer_index].mask, layer_read_mask
                    ).sum(),
                    total=layer_read_mask.sum(),
                ),
            )

            # remove slice values which were just inserted for next layer
            slice_array[empty_patches] = ma.masked

            if slice_array.mask.all():
                logger.debug("slice fully inserted into cube, skipping")
                break

        # report on layer fill status
        logger.debug(
            "cube is %s",
            _percent_full(
                remaining=np.logical_and(out.mask, _cube_read_mask()).sum(),
                total=_cube_read_mask().sum(),
            ),
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
    read_mask: Optional[np.ndarray] = None,
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
            read_mask=read_mask,
        ),
        slice_names=[f"layer-{ii}" for ii in range(target_height)],
        band_names=variables,
        slice_axis_name=slice_axis_name,
        band_axis_name=band_axis_name,
        x_axis_name=x_axis_name,
        y_axis_name=y_axis_name,
    )


def _percent_full(remaining: int, total: int, ndigits: int = 2) -> str:
    return f"{round(100 * (total - remaining) / total, ndigits=ndigits)}% full ({remaining} remaining emtpy pixels)"
