from collections import defaultdict
import logging
import math
import os
from typing import List, Union

import fsspec
import pystac
import rasterio
from affine import Affine
from mapchete import Timer
from mapchete.io import copy, fs_from_path, makedirs, path_is_remote
from mapchete.io.raster import rasterio_write
from rasterio.vrt import WarpedVRT

from mapchete_eo.platforms.sentinel2.types import Resolution

logger = logging.getLogger(__name__)


def path_is_relative(path):
    if path_is_remote(path):
        return False
    else:
        return not os.path.isabs(path)


def asset_href(item: pystac.Item, asset: str) -> str:
    try:
        return item.assets[asset].href
    except KeyError:
        raise KeyError(
            f"no asset named '{asset}' found in assets: {', '.join(item.assets.keys())}"
        )


def get_assets(
    item: pystac.Item,
    assets: List[str],
    dst_dir: str,
    src_fs: fsspec.AbstractFileSystem = None,
    dst_fs: fsspec.AbstractFileSystem = None,
    overwrite: bool = False,
    ignore_if_exists: bool = False,
    resolution: Resolution = Resolution["original"],
    compression: str = "deflate",
    driver: str = "COG",
    item_href_in_dst_dir: bool = True,
    convert_file_extensions: List[str] = [".tif", ".jp2"],
) -> pystac.Item:
    for asset in assets:
        if resolution != Resolution.original and asset_href(item, asset).endswith(
            tuple(convert_file_extensions)
        ):
            item = convert_asset(
                item,
                asset,
                dst_dir,
                src_fs=src_fs,
                dst_fs=dst_fs,
                resolution=resolution.value,
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
                src_fs=src_fs,
                dst_fs=dst_fs,
                overwrite=overwrite,
                ignore_if_exists=ignore_if_exists,
                item_href_in_dst_dir=item_href_in_dst_dir,
            )
    return item


def copy_asset(
    item: pystac.Item,
    asset: str,
    dst_dir: str,
    src_fs: fsspec.AbstractFileSystem = None,
    dst_fs: fsspec.AbstractFileSystem = None,
    overwrite: bool = False,
    ignore_if_exists: bool = False,
    item_href_in_dst_dir: bool = True,
) -> pystac.Item:
    """Copy asset from one place to another."""

    asset_path = asset_href(item, asset)
    output_path = os.path.join(dst_dir, os.path.basename(asset_path))
    dst_fs = dst_fs or src_fs or fs_from_path(output_path)

    # write relative path into asset.href if Item will be in the same directory
    if item_href_in_dst_dir and path_is_relative(output_path):
        item.assets[asset].href = os.path.basename(asset_path)
    else:
        item.assets[asset].href = output_path

    if dst_fs.exists(output_path):
        if ignore_if_exists:
            logger.debug("ignore existing asset %s", output_path)
            return item
        elif overwrite:
            logger.debug("overwrite exsiting asset %s", output_path)
            pass
        else:
            raise IOError(f"{output_path} already exists")
    else:
        makedirs(dst_dir, fs=dst_fs)

    with Timer() as t:
        logger.debug("copy asset %s to %s ...", asset_path, dst_dir)
        copy(
            asset_path,
            output_path,
            src_fs=src_fs,
            dst_fs=dst_fs,
            overwrite=overwrite,
        )
    logger.debug("copied asset '%s' in %s", asset, t)

    return item


def convert_asset(
    item: pystac.Item,
    asset: str,
    dst_dir: str,
    src_fs: fsspec.AbstractFileSystem = None,
    dst_fs: fsspec.AbstractFileSystem = None,
    overwrite: bool = False,
    ignore_if_exists: bool = False,
    resolution: int = 10,
    compression: str = "deflate",
    driver: str = "COG",
    item_href_in_dst_dir: bool = True,
) -> pystac.Item:
    asset_path = asset_href(item, asset)
    output_path = os.path.join(dst_dir, os.path.basename(asset_path))
    dst_fs = dst_fs or src_fs or fs_from_path(output_path)

    # write relative path into asset.href if Item will be in the same directory
    if item_href_in_dst_dir and path_is_relative(output_path):
        item.assets[asset].href = os.path.basename(asset_path)
    else:
        item.assets[asset].href = output_path

    if dst_fs.exists(output_path):
        if ignore_if_exists:
            logger.debug("ignore existing asset %s", output_path)
            return item
        elif overwrite:
            logger.debug("overwrite exsiting asset %s", output_path)
            pass
        else:
            raise IOError(f"{output_path} already exists")
    else:
        makedirs(dst_dir, fs=dst_fs)

    with Timer() as t:
        logger.debug(
            "converting %s to %s using %sm resolution, %s compression and %s driver ...",
            asset_path,
            output_path,
            resolution,
            compression,
            driver,
        )
        with rasterio.open(asset_path, "r") as src:
            meta = src.meta
            src_transform = src.transform
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
                driver=driver,
                transform=dst_transform,
                width=dst_width,
                height=dst_height,
                compress=compression,
            )
            with rasterio_write(output_path, "w", **meta) as dst:
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
