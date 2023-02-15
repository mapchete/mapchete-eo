import logging
from collections import defaultdict
from typing import Dict, List, Union, Any

import numpy as np
import pystac
import xarray as xr
from mapchete.io.raster import read_raster_window
from mapchete.tile import BufferedTile

from mapchete_eo.array.convert import masked_to_xarr

logger = logging.getLogger(__name__)


def items_to_xarray(
    items: List[pystac.Item] = [],
    assets: List[str] = [],
    eo_bands: List[str] = [],
    tile: BufferedTile = None,
    resampling: str = "nearest",
    nodatavals: Union[List, None] = None,
    band_axis_name: str = "bands",
    x_axis_name: str = "x",
    y_axis_name: str = "y",
    time_axis_name: str = "time",
    merge_items_by: Union[str, None] = None,
) -> xr.Dataset:
    """
    Read tile window of STAC Items and merge into a 4D xarray.
    """
    if len(items) == 0:
        raise ValueError("no items to read")
    if merge_items_by is not None:
        items_per_property = group_items_per_property(items, merge_items_by)
        logger.debug(
            "reading %s items in %s groups...", len(items), len(items_per_property)
        )
        return xr.Dataset(
            data_vars={
                data_var_name: merge_items(
                    items=items,
                    assets=assets,
                    eo_bands=eo_bands,
                    tile=tile,
                    resampling=resampling,
                    nodatavals=nodatavals,
                    x_axis_name=x_axis_name,
                    y_axis_name=y_axis_name,
                    time_axis_name=time_axis_name,
                ).to_stacked_array(
                    new_dim=band_axis_name,
                    sample_dims=(x_axis_name, y_axis_name),
                    name=data_var_name,
                )
                for data_var_name, items in items_per_property.items()
            },
        ).transpose(band_axis_name, x_axis_name, y_axis_name)
    else:
        logger.debug("reading %s items...", len(items))
        return xr.Dataset(
            data_vars={
                item.id: item_to_xarray(
                    item=item,
                    assets=assets,
                    eo_bands=eo_bands,
                    tile=tile,
                    resampling=resampling,
                    nodatavals=nodatavals,
                    x_axis_name=x_axis_name,
                    y_axis_name=y_axis_name,
                    time_axis_name=time_axis_name,
                ).to_stacked_array(
                    new_dim=band_axis_name,
                    sample_dims=(x_axis_name, y_axis_name),
                    name=item.id,
                )
                for item in items
            },
            coords={
                time_axis_name: np.array(
                    [i.datetime for i in items], dtype=np.datetime64
                )
            },
        ).transpose(time_axis_name, band_axis_name, x_axis_name, y_axis_name)


def merge_items(
    items: List[pystac.Item] = [], merge_method: str = "first", **kwargs
) -> xr.Dataset:
    if len(items) == 0:
        raise ValueError("no items to merge")
    out = item_to_xarray(items[0], **kwargs)
    # delete attributes because dataset is a merge of multiple items
    out.attrs = dict()
    for item in items[1:]:
        xr = item_to_xarray(item=item, **kwargs)
        if merge_method == "first":
            # replace masked values with values from freshly read xarray
            for variable in out.variables:
                out[variable] = out[variable].where(
                    out[variable] == out[variable].attrs["_FillValue"], xr[variable]
                )
        else:
            raise NotImplementedError(f"unknown merge method: {merge_method}")
    return out


def item_to_xarray(
    item: pystac.Item,
    eo_bands: List[str] = [],
    assets: List[str] = [],
    tile: BufferedTile = None,
    resampling: Union[List[str], str] = "nearest",
    nodatavals: Union[List[float], List[None], float, None] = None,
    x_axis_name: str = "x",
    y_axis_name: str = "y",
    time_axis_name: str = "time",
) -> xr.Dataset:
    """
    Read tile window of STAC Item and merge into a 3D xarray.
    """
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
    return xr.Dataset(
        data_vars={
            data_var_name: asset_to_xarray(
                item=item,
                asset=asset,
                indexes=index,
                tile=tile,
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


def asset_to_xarray(
    item: pystac.Item,
    asset: str,
    indexes: Union[list, int] = 1,
    tile: BufferedTile = None,
    resampling: str = "nearest",
    nodataval: Union[float, None] = None,
    x_axis_name: str = "x",
    y_axis_name: str = "y",
) -> xr.DataArray:
    """
    Read tile window of STAC Items and merge into a 2D xarray.
    """
    logger.debug("reading asset %s and indexes %s ...", asset, indexes)
    return masked_to_xarr(
        read_raster_window(
            item.assets[asset].href,
            indexes=indexes,
            tile=tile,
            resampling=resampling,
            dst_nodata=nodataval,
        ),
        nodataval=nodataval,
        x_axis_name=x_axis_name,
        y_axis_name=y_axis_name,
        name=asset,
        attrs=dict(item_id=item.id),
    )


def eo_bands_to_assets_indexes(item: pystac.Item, eo_bands: List[str]) -> List[tuple]:
    """
    Find out location (asset and band index) of EO band.
    """
    mapping = defaultdict(list)
    for eo_band in eo_bands:
        for asset_name, asset in item.assets.items():
            asset_eo_bands = asset.extra_fields.get("eo:bands")
            if asset_eo_bands:
                for band_idx, band_info in enumerate(asset_eo_bands, 1):
                    if eo_band == band_info.get("name"):
                        mapping[eo_band].append((asset_name, band_idx))

    for eo_band in eo_bands:
        if eo_band not in mapping:
            raise KeyError(f"EO band {eo_band} not found in item assets")
        found = mapping[eo_band]
        if len(found) > 1:
            for asset_name, band_idx in found:
                if asset_name == eo_band:
                    mapping[eo_band] = [(asset_name, band_idx)]
                    break
            else:
                raise ValueError(
                    f"EO band {eo_band} found in multiple assets: {', '.join([f[0] for f in found])}"
                )

    return [mapping[eo_band][0] for eo_band in eo_bands]


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
    else:
        raise KeyError(
            f"item does not have property {property} in its datetime, properties or extra_fields"
        )


def group_items_per_property(items: List[pystac.Item], property: str) -> Dict:
    """Group items per given property."""
    out = defaultdict(list)
    for item in items:
        out[get_item_property(item, property)].append(item)
    return out
