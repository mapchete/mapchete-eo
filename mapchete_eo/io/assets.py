from collections import defaultdict
import logging
import math
from typing import List

import fsspec
import pystac
from affine import Affine
from mapchete import Timer
from mapchete.io import copy, rasterio_open
from mapchete.path import MPath
from rasterio.vrt import WarpedVRT
from typing import Union

logger = logging.getLogger(__name__)


def asset_href(
    item: pystac.Item, asset: str, fs: fsspec.AbstractFileSystem = None
) -> MPath:
    try:
        return MPath(item.assets[asset].href, fs=fs)
    except KeyError:
        raise KeyError(
            f"no asset named '{asset}' found in assets: {', '.join(item.assets.keys())}"
        )


def get_assets(
    item: pystac.Item,
    assets: List[str],
    dst_dir: MPath,
    src_fs: fsspec.AbstractFileSystem = None,
    overwrite: bool = False,
    resolution: Union[None, float, int] = None,
    compression: str = "deflate",
    driver: str = "COG",
    item_href_in_dst_dir: bool = True,
    convert_file_extensions: List[str] = [".tif", ".jp2"],
    ignore_if_exists: bool = False,
) -> pystac.Item:
    for asset in assets:
        if resolution is not None and asset_href(item, asset).endswith(
            tuple(convert_file_extensions)
        ):
            item = convert_asset(
                item,
                asset,
                dst_dir,
                src_fs=src_fs,
                resolution=resolution,
                overwrite=overwrite,
                ignore_if_exists=ignore_if_exists,
                compression=compression,
                driver=driver,
                item_href_in_dst_dir=item_href_in_dst_dir,
            )
        else:
            item = copy_asset(
                item,
                asset,
                dst_dir,
                overwrite=overwrite,
                ignore_if_exists=ignore_if_exists,
                item_href_in_dst_dir=item_href_in_dst_dir,
            )
    return item


def copy_asset(
    item: pystac.Item,
    asset: str,
    dst_dir: MPath,
    src_fs: fsspec.AbstractFileSystem = None,
    overwrite: bool = False,
    item_href_in_dst_dir: bool = True,
    ignore_if_exists: bool = False,
) -> pystac.Item:
    """Copy asset from one place to another."""

    asset_path = asset_href(item, asset, fs=src_fs)
    output_path = dst_dir / asset_path.name

    # write relative path into asset.href if Item will be in the same directory
    if item_href_in_dst_dir and not output_path.is_absolute():
        item.assets[asset].href = asset_path.name
    else:
        item.assets[asset].href = str(output_path)

    # TODO make this check optional
    if output_path.exists():
        if ignore_if_exists:
            logger.debug("ignore existing asset %s", output_path)
            return item
        elif overwrite:
            logger.debug("overwrite exsiting asset %s", output_path)
        else:
            raise IOError(f"{output_path} already exists")
    else:
        dst_dir.makedirs()

    with Timer() as t:
        logger.debug("copy asset %s to %s ...", asset_path, dst_dir)
        copy(
            asset_path,
            output_path,
            overwrite=overwrite,
        )
    logger.debug("copied asset '%s' in %s", asset, t)

    return item


def convert_asset(
    item: pystac.Item,
    asset: str,
    dst_dir: MPath,
    src_fs: fsspec.AbstractFileSystem = None,
    overwrite: bool = False,
    resolution: Union[None, float, int] = None,
    compression: str = "deflate",
    driver: str = "COG",
    item_href_in_dst_dir: bool = True,
    ignore_if_exists: bool = False,
) -> pystac.Item:
    asset_path = asset_href(item, asset, fs=src_fs)
    output_path = dst_dir / asset_path.name

    # write relative path into asset.href if Item will be in the same directory
    if item_href_in_dst_dir and not output_path.is_absolute():
        item.assets[asset].href = asset_path.name
    else:
        item.assets[asset].href = str(output_path)

    # TODO make this check optional
    if output_path.exists():
        if ignore_if_exists:
            logger.debug("ignore existing asset %s", output_path)
            return item
        elif overwrite:
            logger.debug("overwrite exsiting asset %s", output_path)
        else:
            raise IOError(f"{output_path} already exists")
    else:
        dst_dir.makedirs()

    with Timer() as t:
        with rasterio_open(asset_path, "r") as src:
            meta = src.meta.copy()
            src_transform = src.transform
            if resolution:
                logger.debug(
                    "converting %s to %s using %sm resolution, %s compression and %s driver ...",
                    asset_path,
                    output_path,
                    resolution,
                    compression,
                    driver,
                )
                src_res = src.transform[0]
                dst_transform = Affine.from_gdal(
                    *(
                        src_transform[2],
                        resolution,
                        0.0,
                        src_transform[5],
                        0.0,
                        -resolution,
                    )
                )
                dst_width = int(math.ceil(src.width * (src_res / resolution)))
                dst_height = int(math.ceil(src.height * (src_res / resolution)))
                meta.update(
                    transform=dst_transform,
                    width=dst_width,
                    height=dst_height,
                )
            meta.update(
                driver=driver,
                compress=compression,
            )
            with rasterio_open(output_path, "w", **meta) as dst:
                with WarpedVRT(
                    src,
                    width=dst_width,
                    height=dst_height,
                    transform=dst_transform,
                ) as warped:
                    dst.write(warped.read())
    logger.debug("converted asset '%s' in %s", asset, t)

    return item


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
