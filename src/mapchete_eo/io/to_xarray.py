import pystac
import xarray as xr
from mapchete.io.raster import read_raster_window
from mapchete.tile import BufferedTile

from mapchete_eo.array.convert import masked_to_xarr


def items_to_xarray(
    items: list = None,
    assets: list = None,
    tile: BufferedTile = None,
    resampling: str = "nearest",
    nodatavals: list = None,
    band_axis_name: str = "bands",
    x_axis_name: str = "x",
    y_axis_name: str = "y",
    merge_items_by: str = None,
) -> xr.Dataset:
    """
    Read tile window of STAC Items and merge into a 4D xarray.
    """
    coords = {}
    return xr.Dataset(
        data_vars={
            item.id: item_to_xarray(
                item=item,
                assets=assets,
                tile=tile,
                resampling=resampling,
                nodatavals=nodatavals,
                x_axis_name=x_axis_name,
                y_axis_name=y_axis_name,
            ).to_stacked_array(
                new_dim=band_axis_name,
                sample_dims=(x_axis_name, y_axis_name),
                name=item.id,
            )
            for item in items
        },
        coords=coords,
    ).transpose(band_axis_name, x_axis_name, y_axis_name)


def item_to_xarray(
    item: pystac.Item = None,
    assets: list = None,
    tile: BufferedTile = None,
    resampling: list = "nearest",
    nodatavals: list = None,
    x_axis_name: str = "x",
    y_axis_name: str = "y",
) -> xr.Dataset:
    """
    Read tile window of STAC Item and merge into a 3D xarray.
    """
    attrs = dict(
        item.properties,
        id=item.id,
    )
    resampling = (
        resampling
        if isinstance(resampling, list)
        else [resampling for _ in range(len(assets))]
    )
    nodatavals = (
        nodatavals
        if isinstance(nodatavals, list)
        else [nodatavals for _ in range(len(assets))]
    )
    coords = {}
    return xr.Dataset(
        data_vars={
            asset: asset_to_xarray(
                item=item,
                asset=asset,
                tile=tile,
                resampling=resampling,
                nodataval=nodataval,
                x_axis_name=x_axis_name,
                y_axis_name=y_axis_name,
            )
            for asset, resampling, nodataval in zip(assets, resampling, nodatavals)
        },
        coords=coords,
        attrs=attrs,
    )


def asset_to_xarray(
    item: pystac.Item = None,
    asset: str = None,
    tile: BufferedTile = None,
    resampling: str = "nearest",
    nodataval: float = None,
    x_axis_name: str = "x",
    y_axis_name: str = "y",
) -> xr.DataArray:
    """
    Read tile window of STAC Items and merge into a 2D xarray.
    """
    return masked_to_xarr(
        read_raster_window(
            item.assets[asset].href,
            indexes=1,
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
