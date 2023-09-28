import logging
from typing import List, Optional

import numpy as np
import numpy.ma as ma
import pystac
import xarray as xr
from rasterio.enums import Resampling

from mapchete_eo.array.convert import masked_to_xarr_ds
from mapchete_eo.io.products import group_products_per_property
from mapchete_eo.io.to_np_array import products_to_np_array
from mapchete_eo.protocols import EOProductProtocol, GridProtocol
from mapchete_eo.types import MergeMethod, NodataVal, NodataVals

logger = logging.getLogger(__name__)


def products_to_xarray(
    products: List[EOProductProtocol],
    assets: Optional[List[str]] = None,
    eo_bands: Optional[List[str]] = None,
    grid: Optional[GridProtocol] = None,
    resampling: Resampling = Resampling.nearest,
    nodatavals: NodataVals = None,
    slice_axis_name: str = "time",
    band_axis_name: str = "bands",
    x_axis_name: str = "x",
    y_axis_name: str = "y",
    merge_products_by: Optional[str] = None,
    merge_method: MergeMethod = MergeMethod.first,
    raise_empty: bool = True,
    product_read_kwargs: dict = {},
) -> xr.Dataset:
    """Read grid window of EOProducts and merge into a 4D xarray."""
    assets = assets or []
    eo_bands = eo_bands or []
    data_var_names = eo_bands or assets

    # merge products
    if merge_products_by:
        slice_var_names = list(
            tuple(group_products_per_property(products, merge_products_by).keys())
        )
        coords = {merge_products_by: slice_var_names}
        return masked_to_xarr_ds(
            products_to_np_array(
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
            ),
            slice_var_names,
            data_var_names,
            coords=coords,
            slice_axis_name=merge_products_by,
            band_axis_name=band_axis_name,
            x_axis_name=x_axis_name,
            y_axis_name=y_axis_name,
        )

    # don't merge products
    else:
        slice_var_names = [product.item.id for product in products]
        coords = {
            slice_axis_name: list(
                np.array(
                    [product.item.datetime for product in products], dtype=np.datetime64
                )
            )
        }
        return masked_to_xarr_ds(
            products_to_np_array(
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
            ),
            slice_var_names,
            data_var_names,
            slices_attrs=[
                dict(product.item.properties, id=product.item.id)
                for product in products
            ],
            coords=coords,
            slice_axis_name=slice_axis_name,
            band_axis_name=band_axis_name,
            x_axis_name=x_axis_name,
            y_axis_name=y_axis_name,
        )
