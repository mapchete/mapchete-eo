from dataclasses import dataclass
from typing import List

import click
import numpy as np
import pystac
from mapchete.cli.options import opt_debug
from mapchete.io.raster import read_raster_no_crs
from mapchete.path import MPath
from tqdm import tqdm

from mapchete_eo.cli import options_arguments
from mapchete_eo.platforms.sentinel2.product import asset_mpath


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
):
    missing_asset_entries = []
    missing_assets = []
    color_artefacts = False
    for asset in assets:
        if asset not in item.assets:
            missing_asset_entries.append(asset)
        if asset_exists_check:
            path = asset_mpath(item=item, asset=asset)
            if not path.exists():
                missing_assets.append(path)
    if check_thumbnail:
        thumbnail = read_raster_no_crs(item.assets["thumbnail"].href)
        color_artefacts = outlier_pixels_detected(thumbnail)
    return Report(
        item,
        missing_asset_entries=missing_asset_entries,
        missing_assets=missing_assets,
        color_artefacts=color_artefacts,
    )


def outlier_pixels_detected(
    arr: np.ndarray, axis: int = 0, range_threshold: int = 250
) -> bool:
    return (arr.max(axis=axis) - arr.min(axis=axis)).max() >= range_threshold
