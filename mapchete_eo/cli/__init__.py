import click

from mapchete_eo.cli.s2_brdf import s2_brdf
from mapchete_eo.cli.s2_mask import s2_mask
from mapchete_eo.cli.s2_rgb import s2_rgb
from mapchete_eo.cli.static_catalog import static_catalog


@click.group(help="Tools around mapchete EO package.")
@click.pass_context
def eo(ctx):
    ctx.ensure_object(dict)


eo.add_command(s2_brdf)
eo.add_command(s2_mask)
eo.add_command(s2_rgb)
eo.add_command(static_catalog)
