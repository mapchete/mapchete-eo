import click
from mapchete.cli.options import opt_bounds, opt_debug
from pystac import Extent

from mapchete_eo.known_catalogs import E84Sentinel2COGs


def _str_to_list(_, __, value):
    if value:
        return value.split(",")


@click.group(help="Tools around mapchete EO package.")
@click.pass_context
def eo(ctx):
    ctx.ensure_object(dict)


@eo.command()
@click.pass_context
@click.argument("dst_path", type=click.Path())
@opt_bounds
@click.option("--start-time", type=click.STRING, help="Start time")
@click.option("--end-time", type=click.STRING, help="End time")
@click.option(
    "--archive",
    type=click.Choice(["sentinel-s2-l2a-cogs"]),
    default="sentinel-s2-l2a-cogs",
    help="Archive to read from.",
)
@click.option(
    "--collection",
    type=click.STRING,
    help="Data collection to be queried.",
)
@click.option(
    "--endpoint",
    type=click.STRING,
    help="Search endpoint.",
)
@click.option("--name", type=click.STRING, help="Static catalog name.")
@click.option("--description", type=click.STRING, help="Static catalog description.")
@click.option(
    "--assets",
    type=click.STRING,
    callback=_str_to_list,
    help="Also copy/convert assets to catalog.",
)
@click.option(
    "--assets-dst-resolution",
    type=click.INT,
    default=60,
    help="Resample assets to this resolution in meter.",
)
@click.option("--overwrite", "-o", is_flag=True, help="Overwrite existing files.")
@opt_debug
def static_catalog(
    ctx,
    dst_path,
    bounds=None,
    start_time=None,
    end_time=None,
    archive=None,
    collection=None,
    endpoint=None,
    name=None,
    description=None,
    assets=None,
    assets_dst_resolution=None,
    overwrite=False,
    **kwargs,
):
    if archive == "sentinel-s2-l2a-cogs":
        catalog = E84Sentinel2COGs(
            bounds=bounds, start_time=start_time, end_time=end_time
        )
    else:
        raise click.ClickException("archive must be provided")
    if any([bounds is None, start_time is None, end_time is None]):
        raise click.ClickException(
            "--bounds, --start-time and --end-time are mandatory"
        )

    catalog_json = catalog.write_static_catalog(
        dst_path,
        name=name,
        description=description,
        assets=assets,
        assets_dst_resolution=assets_dst_resolution,
        overwrite=overwrite,
    )

    click.echo(f"Catalog successfully written to {catalog_json}")
