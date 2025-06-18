from datetime import datetime
from typing import Any, Literal, Optional

import click
import click_spinner

from shapely.geometry import mapping, MultiPolygon, Polygon, shape

from mapchete.cli.options import opt_bounds, opt_debug
from mapchete.io import fiona_open
from mapchete.path import MPath
from mapchete.types import Bounds

from mapchete_eo.cli import options_arguments
from mapchete_eo.cli.static_catalog import get_catalog
from mapchete_eo.io.products import Slice, products_to_slices
from mapchete_eo.platforms.sentinel2.archives import KnownArchives
from mapchete_eo.platforms.sentinel2.product import S2Product
from mapchete_eo.sort import TargetDateSort
from mapchete_eo.types import TimeRange


@click.command()
@options_arguments.arg_dst_path
@options_arguments.opt_start_time
@options_arguments.opt_end_time
@opt_bounds
@options_arguments.opt_mgrs_tile
@options_arguments.opt_archive
@options_arguments.opt_collection
@options_arguments.opt_endpoint
@options_arguments.opt_catalog_json
@click.option(
    "--format",
    type=click.Choice(["FlatGeobuf", "GeoJSON"]),
    help="Format of output file.",
)
@click.option("--by-slices", is_flag=True, help="Merge product to slices.")
@click.option(
    "--add-index", is_flag=True, help="Add unique indexes to products/slices."
)
@opt_debug
def s2_cat_results(
    dst_path: MPath,
    start_time: datetime,
    end_time: datetime,
    bounds: Optional[Bounds] = None,
    mgrs_tile: Optional[str] = None,
    archive: Optional[KnownArchives] = None,
    collection: Optional[str] = None,
    endpoint: Optional[str] = None,
    catalog_json: Optional[MPath] = None,
    format: Literal["FlatGeobuf", "GeoJSON"] = "FlatGeobuf",
    by_slices: bool = False,
    add_index: bool = False,
    debug: bool = False,
):
    """Write a search result."""
    if catalog_json and endpoint:  # pragma: no cover
        raise click.ClickException(
            "exactly one of --archive, --catalog-json or --endpoint has to be set."
        )
    if any([start_time is None, end_time is None]):  # pragma: no cover
        raise click.ClickException("--start-time and --end-time are mandatory")
    if all([bounds is None, mgrs_tile is None]):  # pragma: no cover
        raise click.ClickException("--bounds or --mgrs-tile are required")
    slice_property_key = "s2:datastrip_id"
    with click_spinner.Spinner(disable=debug):
        catalog = get_catalog(
            catalog_json=catalog_json,
            endpoint=endpoint,
            known_archive=archive,
            collection=collection,
        )
        slices = products_to_slices(
            [
                S2Product.from_stac_item(item)
                for item in catalog.search(
                    time=TimeRange(start=start_time, end=end_time),
                    bounds=bounds,
                    search_kwargs=dict(mgrs_tile=mgrs_tile),
                )
            ],
            group_by_property=slice_property_key if by_slices else None,
            sort=TargetDateSort(target_date=start_time),
        )
    if slices:
        schema = get_schema(by_slices=by_slices, add_index=add_index)
        with fiona_open(
            dst_path, mode="w", schema=schema, crs="EPSG:4326", format=format
        ) as dst:
            for index, _slice in enumerate(slices, start=1):
                # 2025-4 agreed to make outputs multipolygons
                # Convert the _slice.__geom_interface__ to Multipolygon if not the case

                # Ensure the result is always a MultiPolygon even if only single Polygon is returned
                # Else split features should come here as MultiPolygons
                slice_shape = shape(_slice.__geom_interface__)
                if isinstance(slice_shape, Polygon):
                    slice_multipolygon = mapping(MultiPolygon([slice_shape]))
                else:
                    slice_multipolygon = _slice.__geom_interface__

                out_feature = {
                    "geometry": slice_multipolygon,
                    "properties": {
                        key: get_value(_slice, key, index, slice_property_key)
                        for key in schema["properties"].keys()
                    },
                }
                dst.write(out_feature)
    else:
        click.echo("No results found.")


def get_schema(
    by_slices: bool, add_index: bool, geometry_type: str = "MultiPolygon"
) -> dict:
    if by_slices:
        properties = {
            "timestamp": "str",
            "slice_id": "str",
        }
    else:
        properties = {
            "eo:cloud_cover": "float",
            "timestamp": "str",
            "slice_id": "str",
            "product_id": "str",
        }
    if add_index:
        properties.update(index="int")
    return {"geometry": geometry_type, "properties": properties}


def get_value(_slice: Slice, key: str, index: int, slice_property_key: str) -> Any:
    if key == "index":
        return index
    elif key == "slice_id":
        return _slice.get_property(slice_property_key)
    elif key == "product_id":
        return _slice.products[0].item.id
    elif key == "timestamp":
        return _slice.datetime
    else:
        return _slice.get_property(key)
