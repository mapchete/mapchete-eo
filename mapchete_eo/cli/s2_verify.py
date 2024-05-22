import logging
from dataclasses import dataclass
from typing import List, Optional

import click
import numpy as np
import pystac
from mapchete.cli.options import opt_debug
from mapchete.io import copy
from mapchete.io.raster import read_raster_no_crs
from mapchete.path import MPath
from tqdm import tqdm

from mapchete_eo.array.color import outlier_pixels
from mapchete_eo.cli import options_arguments
from mapchete_eo.exceptions import AssetKeyError
from mapchete_eo.platforms.sentinel2.product import asset_mpath

logger = logging.getLogger(__name__)


@dataclass
class Report:
    item: pystac.Item
    missing_asset_entries: List[str]
    missing_assets: List[MPath]
    color_artefacts: bool = False

    def product_broken(self) -> bool:
        return any(
            [
                bool(self.missing_asset_entries),
                bool(self.missing_assets),
                bool(self.color_artefacts),
            ]
        )


@click.command()
@options_arguments.arg_stac_items
@options_arguments.opt_assets
@opt_debug
def s2_verify(
    stac_items: List[MPath],
    assets: List[str] = [],
    asset_exists_check: bool = True,
    **_,
):
    """Verify Sentinel-2 products."""
    assets = assets or []
    for item_path in tqdm(stac_items):
        report = verify_item(
            pystac.Item.from_file(item_path),
            assets=assets,
            asset_exists_check=asset_exists_check,
        )
        for asset in report.missing_asset_entries:
            tqdm.write(f"[ERROR] {report.item.id} has no asset named '{asset}")
        for path in report.missing_assets:
            tqdm.write(
                f"[ERROR] {report.item.id} asset '{asset}' with path {str(path)} does not exist"
            )
        if report.color_artefacts:
            tqdm.write(
                f"[ERROR] {report.item.id} thumbnail ({report.item.assets['thumbnail'].href}) indicates that there are some color artefacts"
            )


def verify_item(
    item: pystac.Item,
    assets: List[str],
    asset_exists_check: bool = False,
    check_thumbnail: bool = True,
    thumbnail_dir: Optional[MPath] = None,
):
    missing_asset_entries = []
    missing_assets = []
    color_artefacts = False
    for asset in assets:
        logger.debug("verify asset %s is available", asset)
        if asset not in item.assets:
            missing_asset_entries.append(asset)
        if asset_exists_check:
            try:
                path = asset_mpath(item=item, asset=asset)
                logger.debug("check if asset %s (%s) exists", asset, str(path))
                if not path.exists():
                    missing_assets.append(path)
            except AssetKeyError:
                missing_asset_entries.append(asset)
    if check_thumbnail:
        thumbnail_href = MPath.from_inp(item.assets["thumbnail"].href)
        logger.debug("check thumbnail %s for artefacts ...", thumbnail_href)
        if thumbnail_dir:
            thumbnail_path = thumbnail_dir / item.id + ".jpg"
            copy(thumbnail_href, thumbnail_path)
        else:
            thumbnail_path = thumbnail_href
        color_artefacts = outlier_pixels_detected(read_raster_no_crs(thumbnail_href))
    return Report(
        item,
        missing_asset_entries=missing_asset_entries,
        missing_assets=missing_assets,
        color_artefacts=color_artefacts,
    )


def outlier_pixels_detected(
    arr: np.ndarray,
    axis: int = 0,
    range_threshold: int = 100,
    allowed_error_percentage: float = 1,
) -> bool:
    """
    Checks whether number of outlier pixels is larger than allowed.

    An outlier pixel is a pixel, where the value range between bands exceeds
    the range_threshold.
    """
    _, width, height = arr.shape
    pixels = width * height
    outliers = outlier_pixels(arr, axis=axis, range_threshold=range_threshold).sum()
    outlier_percent = outliers / pixels * 100
    logger.debug(
        "%s (%s %%) suspicious pixels detected",
        outliers,
        round(outlier_percent, 2),
    )
    return outlier_percent > allowed_error_percentage
