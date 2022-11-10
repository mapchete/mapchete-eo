import logging
import math
import os

import fsspec
import pystac
import rasterio
from affine import Affine
from mapchete import Timer
from mapchete.io import copy, fs_from_path, makedirs
from mapchete.io.raster import rasterio_write
from rasterio.vrt import WarpedVRT

logger = logging.getLogger(__name__)


def copy_assets(
    item: pystac.Item,
    assets: list,
    dst_dir: str,
    src_fs: fsspec.AbstractFileSystem = None,
    dst_fs: fsspec.AbstractFileSystem = None,
    overwrite: bool = False,
) -> str:
    """Copy asset from one place to another."""
    assets = assets if isinstance(assets, list) else [assets]

    logger.debug("copy assets %s to %s ...", assets, dst_dir)

    for asset in assets:
        asset_path = item.assets[asset].href
        output_path = os.path.join(dst_dir, os.path.basename(asset_path))

        with Timer() as t:
            copy(
                asset_path,
                output_path,
                src_fs=src_fs,
                dst_fs=dst_fs,
                overwrite=overwrite,
            )
        logger.debug("copied asset %s in %s", asset, t)

        item.assets[asset].href = output_path

    return item


def convert_assets(
    item: pystac.Item,
    assets: str,
    dst_dir: str,
    src_fs: fsspec.AbstractFileSystem = None,
    dst_fs: fsspec.AbstractFileSystem = None,
    overwrite: bool = False,
    resolution: int = None,
    compression: str = "deflate",
    driver: str = "COG",
):
    assets = assets if isinstance(assets, list) else [assets]

    logger.debug("convert assets %s to %s ...", assets, dst_dir)

    for asset in assets:
        asset_path = item.assets[asset].href
        output_path = os.path.join(dst_dir, os.path.basename(asset_path))
        dst_fs = src_fs or fs_from_path(output_path)

        if not overwrite and dst_fs.exists(output_path):
            raise IOError(f"{output_path} already exists")

        makedirs(dst_dir, fs=dst_fs)

        with Timer() as t:
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
        logger.debug("converted asset %s in %s", asset, t)

        item.assets[asset].href = output_path

    return item
