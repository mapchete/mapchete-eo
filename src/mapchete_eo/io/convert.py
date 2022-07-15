import os

import fsspec
import pystac
from mapchete.io import copy


def copy_asset(
    item: pystac.Item,
    asset: str,
    output_dir: str,
    src_fs: fsspec.AbstractFileSystem = None,
    dst_fs: fsspec.AbstractFileSystem = None,
    overwrite: bool = False,
) -> str:
    """Copy asset from one place to another."""
    asset_path = item.assets[asset].href
    output_path = os.path.join(output_dir, os.path.basename(asset_path))
    copy(asset_path, output_path, src_fs=src_fs, dst_fs=dst_fs, overwrite=overwrite)
    item.assets[asset].href = output_path
    return item
