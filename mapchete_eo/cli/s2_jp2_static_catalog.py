from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from types import TracebackType
from typing import Optional, Type

import click
import tqdm
from fiona.crs import CRS
from mapchete.cli.options import opt_bounds, opt_debug
from mapchete.io.vector import fiona_open
from mapchete.path import MPath
from mapchete.types import Bounds
from pystac import Item
from shapely import prepare

from mapchete_eo.cli import options_arguments
from mapchete_eo.io.items import item_fix_footprint
from mapchete_eo.search.s2_mgrs import InvalidMGRSSquare, S2Tile, bounds_to_geom
from mapchete_eo.time import day_range

logger = logging.getLogger(__name__)


DEFAULT_SCHEMA = {
    "geometry": ("Polygon", "MultiPolygon"),
    "properties": {"id": "str", "path": "str"},
}


@dataclass
class VectorDataSource:
    path: MPath
    schema: Optional[dict] = None
    driver: Optional[str] = "FlatGeobuf"
    crs: Optional[CRS] = CRS.from_epsg(4326)
    features: dict = field(default_factory=dict)

    def write(self, feature_id: str, feature: dict):
        if feature_id not in self.features:
            self.features[feature_id] = dict(
                id=feature_id,
                geometry=feature["geometry"],
                properties=dict(feature["properties"], id=feature_id),
            )

    def __enter__(self) -> VectorDataSource:
        if self.path.exists():
            logger.debug("read existing data from %s", str(self.path))
            with fiona_open(self.path) as src:
                self.features = {
                    feature.properties["id"]: dict(
                        geometry=dict(feature.geometry),
                        properties=dict(feature.properties),
                    )
                    for feature in src
                }

        return self

    def __exit__(
        self,
        exc_type: Optional[Type[Exception]] = None,
        exc: Optional[Exception] = None,
        exc_tb: Optional[TracebackType] = None,
    ):
        if not exc_type:
            logger.debug(f"remove {self.path} if exists ...")
            self.path.rm(ignore_errors=True)
            logger.debug(f"writing to {self.path} ...")
            with fiona_open(
                self.path,
                mode="w",
                driver=self.driver,
                schema=self.schema or DEFAULT_SCHEMA,
                crs=self.crs,
            ) as dst:
                dst.writerecords(list(self.features.values()))


@click.command()
@options_arguments.arg_dst_path
@options_arguments.opt_start_time
@options_arguments.opt_end_time
@opt_bounds
@click.option(
    "--basepath", type=click.Path(path_type=MPath), default="s3://sentinel-s2-l2a-stac/"
)
@opt_debug
def s2_jp2_static_catalog(
    dst_path: MPath,
    start_time: datetime,
    end_time: datetime,
    bounds: Optional[Bounds] = None,
    basepath: MPath = MPath("s3://sentinel-s2-l2a-stac/"),
    **_,
):
    """
    Create a queriable set of static files for AWS_JP2 STAC items.

    - one master file linking spatially to all S2Tile subfiles: index.fgb
    - each entry links to a specific S2Tile file, e.g. tiles/53NQJ.fgb
    - each S2Tile file contains for each STAC item one entry with geometry and href
    """
    bounds = bounds or Bounds(-180, -90, 180, 90)
    aoi = bounds_to_geom(bounds)
    prepare(aoi)
    items_per_tile = defaultdict(list)
    for day in day_range(start_date=start_time, end_date=end_time):
        day_path = basepath / day.strftime("%Y/%m/%d")
        click.echo(f"looking into {day_path} ...")
        try:
            paths = day_path.ls()
        except FileNotFoundError:
            continue
        click.echo(f"found {len(paths)} items")
        for json_path in paths:
            tile_id = json_path.without_suffix().name.split("_")[-1]
            items_per_tile[tile_id].append(json_path)

    index_path = dst_path / "index.fgb"
    s2tile_directory = MPath("s2tiles")
    with VectorDataSource(path=index_path) as index:
        for tile_id, json_paths in tqdm.tqdm(items_per_tile.items()):
            try:
                s2tile = S2Tile.from_tile_id(tile_id)
            except InvalidMGRSSquare as exc:
                logger.debug("omitting S2Tile because of %s", str(exc))
                continue
            if aoi.intersects(s2tile.latlon_geometry):
                tqdm.tqdm.write(f"adding {s2tile.tile_id} ...")
                relative_tile_index_path = s2tile_directory / f"{s2tile.tile_id}.fgb"
                with VectorDataSource(
                    path=dst_path / relative_tile_index_path,
                    schema={
                        "geometry": ("Polygon", "MultiPolygon"),
                        "properties": {"id": "str", "path": "str", "datetime": "str"},
                    },
                ) as tile_index:
                    for json_path in json_paths:
                        item = item_fix_footprint(Item.from_file(json_path))
                        if item.geometry:
                            tile_index.write(
                                item.id,
                                dict(
                                    geometry=dict(item.geometry),
                                    properties=dict(
                                        path=str(json_path), datetime=str(item.datetime)
                                    ),
                                ),
                            )

                index.write(
                    feature_id=s2tile.tile_id,
                    feature=dict(
                        geometry=s2tile.latlon_geometry,
                        properties=dict(
                            path=str(relative_tile_index_path),
                        ),
                    ),
                )
            else:
                tqdm.tqdm.write(f"{s2tile.tile_id} not within bounds")
