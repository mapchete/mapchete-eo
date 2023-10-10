import logging
from typing import List, Optional

import numpy as np
import numpy.ma as ma
import xarray as xr
from rasterio.enums import Resampling

from mapchete_eo.array.convert import to_dataset, to_masked_array
from mapchete_eo.io.products import generate_slices
from mapchete_eo.protocols import EOProductProtocol, GridProtocol
from mapchete_eo.sort import SortMethodConfig, TargetDateSort
from mapchete_eo.types import MergeMethod, NodataVals

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

    # activate generator
    slices = (
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
            sort=sort,
            product_read_kwargs=product_read_kwargs,
            raise_empty=raise_empty,
        )
    )

    # generate first slice to be able to determine dtype and shape of output array
    first_slice = next(slices)
    shape = (target_height, *first_slice.shape)
    out: ma.MaskedArray = ma.masked_array(
        data=np.zeros(shape, dtype=first_slice.dtype),
        mask=np.ones(shape, dtype=first_slice.dtype),
        fill_value=first_slice.fill_value,
    )
    # insert first slice to output cube
    out[0] = first_slice

    if out.mask.any():
        # read slices one by one
        for slice_ in slices:
            # iterate through layers of cube
            for layer_index in range(target_height):
                # go to next layer if layer is full
                if not out[layer_index].mask.any():
                    logger.debug("cube layer %s full, jump to next", layer_index)
                    continue

                # determine empty patches of current layer
                empty_patches = out[layer_index].mask.copy()
                logger.debug(
                    "slice has %s masked pixels", slice_[empty_patches].mask.sum()
                )

                logger.debug(
                    "layer %s has %s masked pixels",
                    layer_index,
                    out[layer_index].mask.sum(),
                )
                logger.debug("fill ...")
                # insert slice data into empty patches of layer
                out[layer_index][empty_patches] = slice_[empty_patches]
                logger.debug(
                    "layer %s has %s masked pixels",
                    layer_index,
                    out[layer_index].mask.sum(),
                )

                # remove slice values which were just inserted for next layer
                slice_[empty_patches] = ma.masked
                if slice_.mask.all():
                    logger.debug("slice fully inserted into cube, skipping")
                    break

            # all filled up? let's get outta here!
            if not out.mask.any():
                break

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
