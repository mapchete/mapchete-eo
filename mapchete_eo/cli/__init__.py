import click

from mapchete_eo.cli.bounds import bounds
from mapchete_eo.cli.s2_brdf import s2_brdf
from mapchete_eo.cli.s2_cat_results import s2_cat_results
from mapchete_eo.cli.s2_find_broken_products import s2_find_broken_products
from mapchete_eo.cli.s2_jp2_static_catalog import s2_jp2_static_catalog
from mapchete_eo.cli.s2_mask import s2_mask
from mapchete_eo.cli.s2_mgrs import s2_mgrs
from mapchete_eo.cli.s2_rgb import s2_rgb
from mapchete_eo.cli.s2_verify import s2_verify
from mapchete_eo.cli.static_catalog import static_catalog


@click.group(help="Tools around mapchete EO package.")
@click.pass_context
def eo(ctx):
    ctx.ensure_object(dict)


eo.add_command(bounds)
eo.add_command(s2_brdf)
eo.add_command(s2_cat_results)
eo.add_command(s2_find_broken_products)
eo.add_command(s2_jp2_static_catalog)
eo.add_command(s2_mask)
eo.add_command(s2_mgrs)
eo.add_command(s2_rgb)
eo.add_command(s2_verify)
eo.add_command(static_catalog)
