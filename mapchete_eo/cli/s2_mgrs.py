import click
from mapchete.cli.options import opt_bounds, opt_debug
from mapchete.io import fiona_open
from mapchete.path import MPath
from mapchete.types import Bounds
from shapely.geometry import mapping

from mapchete_eo.cli import options_arguments
from mapchete_eo.search.s2_mgrs import s2_tiles_from_bounds


@click.command()
@options_arguments.arg_dst_path
@opt_bounds
@opt_debug
def s2_mgrs(
    dst_path: MPath,
    bounds: Bounds,
    **_,
):
    """Save Sentinel-2 tile grid as FlatGeobuf."""
    schema = dict(
        geometry="Polygon",
        properties=dict(
            utm_zone="str",
            latitude_band="str",
            grid_square="str",
            tile_id="str",
        ),
    )
    with fiona_open(
        dst_path, "w", crs="EPSG:4326", driver="FlatGeobuf", schema=schema
    ) as dst:
        for tile in s2_tiles_from_bounds(*bounds):
            dst.write(
                dict(
                    geometry=mapping(tile.latlon_geometry),
                    properties=dict(
                        utm_zone=tile.utm_zone,
                        latitude_band=tile.latitude_band,
                        grid_square=tile.grid_square,
                        tile_id=tile.tile_id,
                    ),
                )
            )
