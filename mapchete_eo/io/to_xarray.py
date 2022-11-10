import logging
import numpy as np
import pystac
from typing import Union, List
import xarray as xr
from mapchete.io.raster import read_raster_window
from mapchete.tile import BufferedTile

from mapchete_eo.array.convert import masked_to_xarr


logger = logging.getLogger(__name__)


def items_to_xarray(
    items: list = None,
    assets: list = None,
    eo_bands: List[str] = None,
    tile: BufferedTile = None,
    resampling: str = "nearest",
    nodatavals: list = None,
    band_axis_name: str = "bands",
    x_axis_name: str = "x",
    y_axis_name: str = "y",
    time_axis_name: str = "time",
    merge_items_by: str = None,
) -> xr.Dataset:
    """
    Read tile window of STAC Items and merge into a 4D xarray.
    """
    if len(items) == 0:  # pragma: no cover
        raise ValueError("no items to read")
    logger.debug("reading %s items...", len(items))
    coords = {}
    coords[time_axis_name] = np.array([i.datetime for i in items], dtype=np.datetime64)
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
        coords=coords,
    ).transpose(time_axis_name, band_axis_name, x_axis_name, y_axis_name)


def item_to_xarray(
    item: pystac.Item = None,
    assets: list = None,
    eo_bands: List[str] = None,
    tile: BufferedTile = None,
    resampling: list = "nearest",
    nodatavals: list = None,
    x_axis_name: str = "X",
    y_axis_name: str = "X",
    time_axis_name: str = "time",
) -> xr.Dataset:
    """
    Read tile window of STAC Item and merge into a 3D xarray.
    """
    if (assets and eo_bands) or (
        assets is None and eo_bands is None
    ):  # pragma: no cover
        raise ValueError("either assets or eo_bands have to be provided")
    assets = [assets] if isinstance(assets, str) else assets
    if eo_bands:
        assets_indexes = eo_bands_to_assets_indexes(item, eo_bands)
    else:
        assets_indexes = [(asset, 1) for asset in assets]
        eo_bands = [None for _ in assets]
    logger.debug("reading %s assets from item %s...", len(assets_indexes), item.id)
    attrs = dict(
        item.properties,
        id=item.id,
    )
    resampling = (
        resampling
        if isinstance(resampling, list)
        else [resampling for _ in range(len(assets_indexes))]
    )
    nodatavals = (
        nodatavals
        if isinstance(nodatavals, list)
        else [nodatavals for _ in range(len(assets_indexes))]
    )
    coords = {}
    return xr.Dataset(
        data_vars={
            eo_band
            or asset: asset_to_xarray(
                item=item,
                asset=asset,
                indexes=index,
                tile=tile,
                resampling=resampling,
                nodataval=nodataval,
                x_axis_name=x_axis_name,
                y_axis_name=y_axis_name,
            )
            for eo_band, (asset, index), resampling, nodataval in zip(
                eo_bands, assets_indexes, resampling, nodatavals
            )
        },
        coords=coords,
        attrs=attrs,
    )


def asset_to_xarray(
    item: pystac.Item = None,
    asset: str = None,
    indexes: Union[list, int] = 1,
    tile: BufferedTile = None,
    resampling: str = "nearest",
    nodataval: float = None,
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
    out = []
    for eo_band in eo_bands:
        eo_band_found = False
        for asset_name, asset in item.assets.items():
            asset_found = None
            asset_eo_bands = asset.extra_fields.get("eo:bands")
            if asset_eo_bands:
                for band_idx, band_info in enumerate(asset_eo_bands, 1):
                    if eo_band == band_info.get("name"):
                        if asset_found:  # pragma: no cover
                            raise ValueError(
                                "EO band %s found in multiple assets (%s, %s)",
                                eo_band,
                                asset_name,
                                asset_found,
                            )
                        else:
                            out.append((asset_name, band_idx))
                            asset_found = asset_name
                            eo_band_found = True
        if not eo_band_found:
            raise KeyError(f"EO band {eo_band} not found in item assets")
    return out
