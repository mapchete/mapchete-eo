from datetime import datetime
from typing import List, Optional

import click
from mapchete.cli.options import opt_bounds, opt_debug
from mapchete.path import MPath
from mapchete.types import Bounds
from tqdm import tqdm

from mapchete_eo.cli import options_arguments
from mapchete_eo.cli.s2_verify import verify_item
from mapchete_eo.platforms.sentinel2.source import Sentinel2Source
from mapchete_eo.product import add_to_blacklist, blacklist_products
from mapchete_eo.types import TimeRange


@click.command()
@opt_bounds
@options_arguments.opt_start_time
@options_arguments.opt_end_time
@options_arguments.opt_source
@options_arguments.opt_assets
@options_arguments.opt_blacklist
@options_arguments.opt_thumbnail_dir
@opt_debug
def s2_find_broken_products(
    start_time: datetime,
    end_time: datetime,
    bounds: Optional[Bounds] = None,
    mgrs_tile: Optional[str] = None,
    source: Sentinel2Source = Sentinel2Source(collection="EarthSearch"),
    assets: List[str] = [],
    asset_exists_check: bool = True,
    blacklist: MPath = MPath("s3://eox-mhub-cache/blacklist.txt"),
    thumbnail_dir: Optional[MPath] = None,
    **__,
):
    """Find broken Sentinel-2 products."""
    if any([start_time is None, end_time is None]):  # pragma: no cover
        raise click.ClickException("--start-time and --end-time are mandatory")
    if all([bounds is None, mgrs_tile is None]):  # pragma: no cover
        raise click.ClickException("--bounds or --mgrs-tile are required")
    catalog = source.get_catalog()
    blacklisted_products = blacklist_products(blacklist)
    for item in tqdm(
        catalog.search(
            time=TimeRange(start=start_time, end=end_time),
            bounds=bounds,
            search_kwargs=dict(mgrs_tile=mgrs_tile),
        )
    ):
        report = verify_item(
            item,
            assets=assets,
            asset_exists_check=asset_exists_check,
            thumbnail_dir=thumbnail_dir,
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
        if report.product_broken():
            if report.item.get_self_href() in blacklisted_products:
                tqdm.write(f"product {report.item.id} already in blacklist")
            elif click.confirm(
                f"should product {report.item.id} be added to the blacklist ({str(blacklist)})"
            ):
                add_to_blacklist(
                    report.item.get_self_href(),
                    blacklist=blacklist,
                )
