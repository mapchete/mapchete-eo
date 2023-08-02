from multiprocessing.sharedctypes import Value
import click
from mapchete.cli.options import opt_bounds, opt_debug
import tqdm
from typing import Union

from mapchete_eo.platforms.sentinel2.base import AWSL2ACOGv1
from mapchete_eo.platforms.sentinel2.types import Resolution
from mapchete_eo.search import STACSearchCatalog, STACStaticCatalog


class TqdmUpTo(tqdm.tqdm):
    """Provides `update_to(n)` which uses `tqdm.update(delta_n)`."""

    def update_to(self, n: int = 1, nsize: int = 1, total: Union[int, None] = None):
        """
        n  : int, optional
            Number of blocks transferred so far [default: 1].
        nsize  : int, optional
            Size of each block (in tqdm units) [default: 1].
        total  : int, optional
            Total size (in tqdm units). If [default: None] remains unchanged.
        """
        if total is not None:
            self.total = total
        return self.update(n * nsize - self.n)  # also sets self.n = b * bsize


def _str_to_list(_, __, value):
    if value:
        return value.split(",")


def _str_to_resolution(_, __, value):
    if value:
        return Resolution[value]


@click.group(help="Tools around mapchete EO package.")
@click.pass_context
def eo(ctx):
    ctx.ensure_object(dict)


@eo.command()
@click.pass_context
@click.argument("dst_path", type=click.Path())
@opt_bounds
@click.option("--mgrs-tile", type=click.STRING)
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
@click.option(
    "--catalog-json",
    type=click.STRING,
    help="JSON file for a static catalog.",
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
    type=click.Choice(list(Resolution.__members__.keys())),
    default="original",
    show_default=True,
    callback=_str_to_resolution,
    help="Resample assets to this resolution in meter.",
)
@click.option("--overwrite", "-o", is_flag=True, help="Overwrite existing files.")
@opt_debug
def static_catalog(
    ctx,
    dst_path,
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
    overwrite=False,
    **kwargs,
):
    selector = {
        "archive": archive,
        "catalog-json": catalog_json,
        "endpoint": endpoint,
    }
    if len([v for v in selector.values() if v is not None]) != 1:
        raise click.ClickException(
            "exactly one of --archive, --catalog-json or --endpoint has to be set."
        )
    if any([start_time is None, end_time is None]):
        raise click.ClickException("--start-time and --end-time are mandatory")
    if all([bounds is None, mgrs_tile is None]):
        raise click.ClickException("--bounds and --mgrs-tile are required")

    if archive:
        if archive == "sentinel-s2-l2a-cogs":
            catalog = AWSL2ACOGv1(
                bounds=bounds,
                start_time=start_time,
                end_time=end_time,
                mgrs_tile=mgrs_tile,
            ).catalog
        else:
            raise ValueError(
                "currently ony archive 'sentinel-s2-l2a-cogs' is supported"
            )
    if catalog_json:
        catalog = STACStaticCatalog(
            baseurl=catalog_json,
            bounds=bounds,
            start_time=start_time,
            end_time=end_time,
        )
    if endpoint:
        catalog = STACSearchCatalog(
            baseurl=endpoint,
            bounds=bounds,
            start_time=start_time,
            end_time=end_time,
        )

    with TqdmUpTo(unit="products", unit_scale=True, miniters=1) as progress:
        catalog_json = catalog.write_static_catalog(
            dst_path,
            name=name,
            description=description,
            assets=assets,
            assets_dst_resolution=assets_dst_resolution,
            overwrite=overwrite,
            progress_callback=progress.update_to,
        )

    click.echo(f"Catalog successfully written to {catalog_json}")
