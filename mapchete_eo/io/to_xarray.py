import logging
from collections import defaultdict
from typing import Any, Dict, List, Union

import numpy as np
import numpy.ma as ma
import pystac
import xarray as xr
from mapchete.io import rasterio_open
from mapchete.path import MPath
from rasterio.enums import Resampling

from mapchete_eo.array.convert import masked_to_xarr, xarr_to_masked
from mapchete_eo.io.assets import eo_bands_to_assets_indexes
from mapchete_eo.io.mapchete_io_raster import read_raster
from mapchete_eo.io.path import absolute_asset_path
from mapchete_eo.protocols import EOProductProtocol, GridProtocol
from mapchete_eo.types import MergeMethod, NodataVal, NodataVals

logger = logging.getLogger(__name__)


def products_to_xarray(
    products: List[EOProductProtocol] = [],
    assets: List[str] = [],
    eo_bands: List[str] = [],
    grid: Union[GridProtocol, None] = None,
    resampling: Resampling = Resampling.nearest,
    nodatavals: NodataVals = None,
    band_axis_name: str = "bands",
    x_axis_name: str = "x",
    y_axis_name: str = "y",
    time_axis_name: str = "time",
    merge_products_by: Union[str, None] = None,
    merge_method: Union[MergeMethod, str] = MergeMethod.first,
) -> xr.Dataset:
    """Read grid window of EOProducts and merge into a 4D xarray."""

    if len(products) == 0:
        raise ValueError("no products to read")

    # don't merge products
    if merge_products_by is None:
        logger.debug("reading %s products...", len(products))
        return xr.Dataset(
            data_vars={
                product.item.id: product.read(
                    assets=assets,
                    eo_bands=eo_bands,
                    grid=grid,
                    resampling=resampling,
                    nodatavals=nodatavals,
                    x_axis_name=x_axis_name,
                    y_axis_name=y_axis_name,
                    time_axis_name=time_axis_name,
                ).to_stacked_array(
                    new_dim=band_axis_name,
                    sample_dims=(x_axis_name, y_axis_name),
                    name=product.item.id,
                )
                for product in products
            },
            coords={
                time_axis_name: np.array(
                    [product.item.datetime for product in products], dtype=np.datetime64
                )
            },
        ).transpose(time_axis_name, band_axis_name, x_axis_name, y_axis_name)

    # merge products
    else:
        products_per_property = group_products_per_property(products, merge_products_by)
        logger.debug(
            "reading %s products in %s groups...",
            len(products),
            len(products_per_property),
        )
        return xr.Dataset(
            data_vars={
                data_var_name: merge_products(
                    products=products,
                    merge_method=merge_method,
                    product_read_kwargs=dict(
                        assets=assets,
                        eo_bands=eo_bands,
                        grid=grid,
                        resampling=resampling,
                        nodatavals=nodatavals,
                        x_axis_name=x_axis_name,
                        y_axis_name=y_axis_name,
                        time_axis_name=time_axis_name,
                    ),
                ).to_stacked_array(
                    new_dim=band_axis_name,
                    sample_dims=(x_axis_name, y_axis_name),
                    name=data_var_name,
                )
                for data_var_name, products in products_per_property.items()
            },
            coords={merge_products_by: list(products_per_property.keys())},
        ).transpose(merge_products_by, band_axis_name, x_axis_name, y_axis_name)


def merge_products(
    products: List[EOProductProtocol] = [],
    merge_method: Union[MergeMethod, str] = MergeMethod.first,
    product_read_kwargs: dict = {},
) -> xr.Dataset:
    merge_method = (
        merge_method
        if isinstance(merge_method, MergeMethod)
        else MergeMethod[merge_method]
    )
    if len(products) == 0:
        raise ValueError("no products to merge")
    out = products[0].read(**product_read_kwargs)
    # delete attributes because dataset is a merge of multiple items
    out.attrs = dict()

    # nothing to merge here
    if len(products) == 1:
        return out

    # first pixels first
    if merge_method == MergeMethod.first:
        for product in products[1:]:
            xr = product.read(**product_read_kwargs)
            # replace masked values with values from freshly read xarray
            for variable in out.variables:
                out[variable] = out[variable].where(
                    out[variable] == out[variable].attrs["_FillValue"], xr[variable]
                )

    # read all and average
    elif merge_method == MergeMethod.average:
        full_stack = [
            out,
            *[product.read(**product_read_kwargs) for product in products[1:]],
        ]
        for variable in out.variables:
            out[variable] = masked_to_xarr(
                ma.stack([xarr_to_masked(xarr[variable]) for xarr in full_stack])
                .mean(axis=0)
                .astype(out[variable].dtype, copy=False)
            )

    else:
        raise NotImplementedError(f"unknown merge method: {merge_method}")

    return out


def _check_params(item, eo_bands, assets, resampling, nodatavals):
    if (len(eo_bands) and len(assets)) or (not len(eo_bands) and not len(assets)):
        raise ValueError("either assets or eo_bands have to be provided")
    if eo_bands:
        assets_indexes = eo_bands_to_assets_indexes(item, eo_bands)
        data_var_names = eo_bands
    else:
        assets_indexes = [(asset, 1) for asset in assets]
        data_var_names = assets
    logger.debug("reading %s assets from item %s...", len(assets_indexes), item.id)
    attrs = dict(
        item.properties,
        id=item.id,
    )
    expanded_resamplings = (
        resampling
        if isinstance(resampling, list)
        else [resampling for _ in range(len(assets_indexes))]
    )
    expanded_nodatavals = (
        nodatavals
        if isinstance(nodatavals, list)
        else [nodatavals for _ in range(len(assets_indexes))]
    )
    return (
        assets_indexes,
        data_var_names,
        attrs,
        expanded_resamplings,
        expanded_nodatavals,
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
    time_axis_name: str = "time",
) -> xr.Dataset:
    """
    Read grid window of STAC Item and merge into a 3D xarray.
    """
    (
        assets_indexes,
        data_var_names,
        attrs,
        expanded_resamplings,
        expanded_nodatavals,
    ) = _check_params(item, eo_bands, assets, resampling, nodatavals)
    return xr.Dataset(
        data_vars={
            data_var_name: asset_to_xarray(
                item=item,
                asset=asset,
                indexes=index,
                grid=grid,
                resampling=expanded_resampling,
                nodataval=nodataval,
                x_axis_name=x_axis_name,
                y_axis_name=y_axis_name,
            )
            for data_var_name, (asset, index), expanded_resampling, nodataval in zip(
                data_var_names,
                assets_indexes,
                expanded_resamplings,
                expanded_nodatavals,
            )
        },
        coords={},
        attrs=attrs,
    )


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
    assets_indexes, _, _, expanded_resamplings, expanded_nodatavals = _check_params(
        item, eo_bands, assets, resampling, nodatavals
    )
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
                assets_indexes, expanded_resamplings, expanded_nodatavals
            )
        ]
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


def get_item_property(item: pystac.Item, property: str) -> Any:
    """
    Return item property.

    A valid property can be a special property like "year" from the items datetime property
    or any key in the item properties or extra_fields.

    Search order of properties is based on the pystac LayoutTemplate search order:

    https://pystac.readthedocs.io/en/stable/_modules/pystac/layout.html#LayoutTemplate
    - The object's attributes
    - Keys in the ``properties`` attribute, if it exists.
    - Keys in the ``extra_fields`` attribute, if it exists.

    Some special keys can be used in template variables:

    +--------------------+--------------------------------------------------------+
    | Template variable  | Meaning                                                |
    +====================+========================================================+
    | ``year``           | The year of an Item's datetime, or                     |
    |                    | start_datetime if datetime is null                     |
    +--------------------+--------------------------------------------------------+
    | ``month``          | The month of an Item's datetime, or                    |
    |                    | start_datetime if datetime is null                     |
    +--------------------+--------------------------------------------------------+
    | ``day``            | The day of an Item's datetime, or                      |
    |                    | start_datetime if datetime is null                     |
    +--------------------+--------------------------------------------------------+
    | ``date``           | The date (iso format) of an Item's                     |
    |                    | datetime, or start_datetime if datetime is null        |
    +--------------------+--------------------------------------------------------+
    | ``collection``     | The collection ID of an Item's collection.             |
    +--------------------+--------------------------------------------------------+
    """
    if property in ["year", "month", "day", "date", "datetime"]:
        if item.datetime is None:
            raise ValueError(
                f"STAC item has no datetime attached, thus cannot get property {property}"
            )
        elif property == "date":
            return item.datetime.date().isoformat()
        elif property == "datetime":
            return item.datetime
        else:
            return item.datetime.__getattribute__(property)
    elif property == "collection":
        return item.collection_id
    elif property in item.properties:
        return item.properties[property]
    elif property in item.extra_fields:
        return item.extra_fields[property]
    elif property == "stac_extensions":
        return item.stac_extensions
    else:
        raise KeyError(
            f"item does not have property {property} in its datetime, properties "
            f"({', '.join(item.properties.keys())}) or extra_fields "
            f"({', '.join(item.extra_fields.keys())})"
        )


def group_products_per_property(
    products: List[EOProductProtocol], property: str
) -> Dict:
    """Group products per given property."""
    out = defaultdict(list)
    for product in products:
        out[product.get_property(property)].append(product)
    return out
