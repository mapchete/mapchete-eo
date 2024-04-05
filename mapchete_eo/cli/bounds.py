import click
import pystac
from mapchete.cli.options import opt_debug
from mapchete.path import MPath

from mapchete_eo.cli import options_arguments
from mapchete_eo.io.items import item_fix_footprint


@click.command()
@options_arguments.arg_stac_item
@opt_debug
def bounds(
    stac_item: MPath,
    **_,
):
    """Prints bounds of STAC item."""
    item = item_fix_footprint(pystac.Item.from_file(stac_item))
    if item.bbox:
        click.echo(f"{' '.join(map(str, item.bbox))}")
    else:
        click.echo("item does not have a bounding box")
