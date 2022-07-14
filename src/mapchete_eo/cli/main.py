import click
from mapchete.cli.options import opt_bounds
from pystac import Extent
from pystac.collection import Collection

from mapchete_eo.discovery import STACSearchCatalog


@click.group(help="Tools around mapchete EO package.")
@click.pass_context
def eo(ctx):
    ctx.ensure_object(dict)


@eo.command()
@click.pass_context
@opt_bounds
@click.option("--start-time", type=click.STRING, help="Start time")
@click.option("--end-time", type=click.STRING, help="End time")
@click.option(
    "--collection",
    type=click.Choice(["sentinel-s2-l2a-cogs"]),
    default="sentinel-s2-l2a-cogs",
    help="Data collection to be queried.",
)
@click.option(
    "--baseurl",
    type=click.STRING,
    default="https://earth-search.aws.element84.com/v0/",
    help="Search endpoint.",
)
def search(ctx, collection=None, **kwargs):
    raise NotImplementedError
