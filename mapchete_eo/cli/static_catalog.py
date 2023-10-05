import click
from mapchete.cli.options import opt_bounds, opt_debug

from mapchete_eo.cli import options_arguments
from mapchete_eo.io.profiles import rio_profiles
from mapchete_eo.platforms.sentinel2 import S2Metadata
from mapchete_eo.platforms.sentinel2.config import AWSL2ACOGv1
from mapchete_eo.platforms.sentinel2.types import Resolution
from mapchete_eo.search import STACSearchCatalog, STACStaticCatalog
from mapchete_eo.types import TimeRange


@click.command()
@options_arguments.arg_dst
@opt_bounds
@options_arguments.opt_mgrs_tile
@options_arguments.opt_start_time
@options_arguments.opt_end_time
@options_arguments.opt_archive
@options_arguments.opt_collection
@options_arguments.opt_endpoint
@options_arguments.opt_catalog_json
@options_arguments.opt_name
@options_arguments.opt_description
@options_arguments.opt_assets_copy
@options_arguments.opt_assets_dst_resolution
@options_arguments.opt_assets_dst_rio_profile
@options_arguments.opt_copy_metadata
@options_arguments.opt_overwrite
@opt_debug
def static_catalog(
    dst,
    bounds=None,
    mgrs_tile=None,
    start_time=None,
    end_time=None,
    archive=None,
    collection=None,
    endpoint=None,
    catalog_json=None,
    name=None,
    description=None,
    assets=None,
    assets_dst_resolution=None,
    assets_dst_rio_profile=None,
    copy_metadata=False,
    overwrite=False,
    **kwargs,
):
    if catalog_json and endpoint:  # pragma: no cover
        raise click.ClickException(
            "exactly one of --archive, --catalog-json or --endpoint has to be set."
        )
    if any([start_time is None, end_time is None]):  # pragma: no cover
        raise click.ClickException("--start-time and --end-time are mandatory")
    if all([bounds is None, mgrs_tile is None]):  # pragma: no cover
        raise click.ClickException("--bounds or --mgrs-tile are required")

    if catalog_json:
        catalog = STACStaticCatalog(
            baseurl=catalog_json,
            bounds=bounds,
            time=TimeRange(
                start=start_time,
                end=end_time,
            ),
        )
    elif endpoint:
        catalog = STACSearchCatalog(
            endpoint=endpoint,
            collections=[collection],
            bounds=bounds,
            time=TimeRange(
                start=start_time,
                end=end_time,
            ),
        )
    else:
        if archive == "sentinel-s2-l2a-cogs":
            catalog = AWSL2ACOGv1(
                bounds=bounds,
                time=TimeRange(
                    start=start_time,
                    end=end_time,
                ),
                mgrs_tile=mgrs_tile,
            ).catalog
        else:  # pragma: no cover
            raise ValueError(
                "currently ony archive 'sentinel-s2-l2a-cogs' is supported"
            )

    with options_arguments.TqdmUpTo(
        unit="products", unit_scale=True, miniters=1, disable=opt_debug
    ) as progress:
        catalog_json = catalog.write_static_catalog(
            dst,
            name=name,
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
