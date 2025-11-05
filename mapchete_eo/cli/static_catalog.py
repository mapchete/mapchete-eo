from datetime import datetime
from typing import List, Optional

import click
from mapchete.cli.options import opt_bounds, opt_debug
from mapchete.path import MPath
from mapchete.types import Bounds
from rasterio.profiles import Profile

from mapchete_eo.cli import options_arguments
from mapchete_eo.platforms.sentinel2 import S2Metadata
from mapchete_eo.platforms.sentinel2.source import Sentinel2Source
from mapchete_eo.platforms.sentinel2.types import Resolution
from mapchete_eo.types import TimeRange


@click.command()
@options_arguments.arg_dst_path
@opt_bounds
@options_arguments.opt_mgrs_tile
@options_arguments.opt_start_time
@options_arguments.opt_end_time
@options_arguments.opt_source
@options_arguments.opt_name
@options_arguments.opt_description
@options_arguments.opt_assets
@options_arguments.opt_assets_dst_resolution
@options_arguments.opt_assets_dst_rio_profile
@options_arguments.opt_copy_metadata
@options_arguments.opt_overwrite
@opt_debug
def static_catalog(
    dst_path: MPath,
    start_time: datetime,
    end_time: datetime,
    bounds: Optional[Bounds] = None,
    mgrs_tile: Optional[str] = None,
    source: Sentinel2Source = Sentinel2Source(collection="EarthSearch"),
    name: Optional[str] = None,
    description: Optional[str] = None,
    assets: Optional[List[str]] = None,
    assets_dst_resolution: Resolution = Resolution.original,
    assets_dst_rio_profile: Optional[Profile] = None,
    copy_metadata: bool = False,
    overwrite: bool = False,
    **__,
):
    """Write a static STAC catalog for selected area."""
    if any([start_time is None, end_time is None]):  # pragma: no cover
        raise click.ClickException("--start-time and --end-time are mandatory")
    if all([bounds is None, mgrs_tile is None]):  # pragma: no cover
        raise click.ClickException("--bounds or --mgrs-tile are required")
    catalog = source.get_catalog()
    if hasattr(catalog, "write_static_catalog"):
        with options_arguments.TqdmUpTo(
            unit="products", unit_scale=True, miniters=1, disable=opt_debug
        ) as progress:
            catalog_json = catalog.write_static_catalog(
                dst_path,
                name=name,
                bounds=bounds,
                time=TimeRange(
                    start=start_time,
                    end=end_time,
                ),
                search_kwargs=dict(mgrs_tile=mgrs_tile),
                description=description,
                assets=assets,
                assets_dst_resolution=assets_dst_resolution.value,
                assets_convert_profile=assets_dst_rio_profile,
                copy_metadata=copy_metadata,
                metadata_parser_classes=(S2Metadata,),
                overwrite=overwrite,
                progress_callback=progress.update_to,
            )

        click.echo(f"Catalog successfully written to {catalog_json}")

    else:
        raise AttributeError(
            f"catalog {catalog} does not support writing a static version"
        )
