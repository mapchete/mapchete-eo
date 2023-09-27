import logging
from typing import List, Optional, Union

import numpy as np
import numpy.ma as ma
import pystac
import xarray as xr
from rasterio.enums import Resampling

from mapchete_eo.array.convert import masked_to_xarr, masked_to_xarr_ds
from mapchete_eo.io.products import group_products_per_property
from mapchete_eo.io.to_np_array import (
    asset_to_np_array,
    item_to_np_array,
    products_to_np_array,
)
from mapchete_eo.protocols import EOProductProtocol, GridProtocol
from mapchete_eo.types import MergeMethod, NodataVal, NodataVals

logger = logging.getLogger(__name__)


def products_to_xarray(
    products: List[EOProductProtocol] = [],
    assets: List[str] = [],
    eo_bands: List[str] = [],
    grid: Optional[GridProtocol] = None,
    resampling: Resampling = Resampling.nearest,
    nodatavals: NodataVals = None,
    band_axis_name: str = "bands",
    x_axis_name: str = "x",
    y_axis_name: str = "y",
    time_axis_name: str = "time",
    merge_products_by: Optional[str] = None,
    merge_method: Union[MergeMethod, str] = MergeMethod.first,
    product_read_kwargs: dict = {},
) -> xr.Dataset:
    """Read grid window of EOProducts and merge into a 4D xarray."""
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
            ),
            slice_var_names,
            data_var_names,
            coords=coords,
            first_axis_name=merge_products_by,
            band_axis_name=band_axis_name,
            x_axis_name=x_axis_name,
            y_axis_name=y_axis_name,
        )

    # don't merge products
    else:
        slice_var_names = [product.item.id for product in products]
        coords = {
            time_axis_name: list(
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
            ),
            slice_var_names,
            data_var_names,
            slices_attrs=[
                dict(product.item.properties, id=product.item.id)
                for product in products
            ],
            coords=coords,
            first_axis_name=time_axis_name,
            band_axis_name=band_axis_name,
            x_axis_name=x_axis_name,
            y_axis_name=y_axis_name,
        )


def item_to_xarray(
    item: pystac.Item,
    eo_bands: List[str] = [],
    assets: List[str] = [],
    grid: Union[GridProtocol, None] = None,
    resampling: Resampling = Resampling.nearest,
    nodatavals: NodataVals = None,
    x_axis_name: str = "x",
    y_axis_name: str = "y",
    # TODO: do we need this axis name?
    time_axis_name: str = "time",
) -> xr.Dataset:
    """
    Read grid window of STAC Item and merge into a 3D xarray.
    """
    return xr.Dataset(
        data_vars={
            data_var_name: masked_to_xarr(
                band,
                nodataval=band.fill_value,
                x_axis_name=x_axis_name,
                y_axis_name=y_axis_name,
                name=data_var_name,
                attrs=dict(item_id=item.id),
            )
            for data_var_name, band in zip(
                eo_bands or assets,
                item_to_np_array(
                    item=item,
                    eo_bands=eo_bands,
                    assets=assets,
                    grid=grid,
                    resampling=resampling,
                    nodatavals=nodatavals,
                ),
            )
        },
        coords={},
        attrs=dict(
            item.properties,
            id=item.id,
        ),
    )


def asset_to_xarray(
    item: pystac.Item,
    asset: str,
    indexes: Union[list, int] = 1,
    grid: Union[GridProtocol, None] = None,
    resampling: Resampling = Resampling.nearest,
    nodataval: NodataVal = None,
    x_axis_name: str = "x",
    y_axis_name: str = "y",
) -> xr.DataArray:
    """
    Read grid window of STAC Items and merge into a 2D xarray.
    """
    return masked_to_xarr(
        asset_to_np_array(
            item,
            asset,
            indexes=indexes,
            grid=grid,
            resampling=resampling,
            nodataval=nodataval,
        ),
        nodataval=nodataval,
        x_axis_name=x_axis_name,
        y_axis_name=y_axis_name,
        name=asset,
        attrs=dict(item_id=item.id),
    )
