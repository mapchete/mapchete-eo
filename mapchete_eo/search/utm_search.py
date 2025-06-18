import datetime
import logging
from typing import Any, Callable, Dict, Generator, List, Optional, Set, Union

from mapchete.io.vector import fiona_open
from mapchete.path import MPath, MPathLike
from mapchete.types import Bounds, BoundsLike
from pystac.collection import Collection
from pystac.item import Item
from shapely.errors import GEOSException
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from mapchete_eo.exceptions import ItemGeometryError
from mapchete_eo.product import blacklist_products
from mapchete_eo.search.base import (
    CatalogSearcher,
    StaticCatalogWriterMixin,
    filter_items,
)
from mapchete_eo.search.config import UTMSearchConfig
from mapchete_eo.search.s2_mgrs import S2Tile, s2_tiles_from_bounds
from mapchete_eo.settings import mapchete_eo_settings
from mapchete_eo.time import day_range, to_datetime
from mapchete_eo.types import TimeRange

logger = logging.getLogger(__name__)


class UTMSearchCatalog(StaticCatalogWriterMixin, CatalogSearcher):
    endpoint: str
    id: str
    day_subdir_schema: str
    stac_json_endswith: str
    description: str
    stac_extensions: List[str]
    blacklist: Set[str] = (
        blacklist_products(mapchete_eo_settings.blacklist)
        if mapchete_eo_settings.blacklist
        else set()
    )
    config_cls = UTMSearchConfig

    def __init__(
        self,
        endpoint: Optional[MPathLike] = None,
        collections: List[str] = [],
        stac_item_modifiers: Optional[List[Callable[[Item], Item]]] = None,
    ):
        self.endpoint = endpoint or self.endpoint
        if len(collections) == 0:  # pragma: no cover
            raise ValueError("no collections provided")
        self.collections = collections
        self.eo_bands = self._eo_bands()
        self.stac_item_modifiers = stac_item_modifiers

    def search(
        self,
        time: Optional[Union[TimeRange, List[TimeRange]]] = None,
        bounds: Optional[BoundsLike] = None,
        area: Optional[BaseGeometry] = None,
        search_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Generator[Item, None, None]:
        config = self.config_cls(**search_kwargs or {})
        if bounds:
            bounds = Bounds.from_inp(bounds)

        for item in filter_items(
            self._raw_search(time=time, bounds=bounds, area=area),
            max_cloud_cover=config.max_cloud_cover,
        ):
            yield item

    def _raw_search(
        self,
        time: Optional[Union[TimeRange, List[TimeRange]]] = None,
        bounds: Optional[Bounds] = None,
        area: Optional[BaseGeometry] = None,
        config: UTMSearchConfig = UTMSearchConfig(),
    ) -> Generator[Item, None, None]:
        if time is None:
            raise ValueError("time must be given")
        if area is not None and area.is_empty:
            return
        if area is not None:
            area = area
            bounds = Bounds.from_inp(area)
        elif bounds is not None:
            bounds = Bounds.from_inp(bounds)
            area = shape(bounds)
        for time_range in time if isinstance(time, list) else [time]:
            start_time = (
                time_range.start
                if isinstance(time_range.start, datetime.date)
                else datetime.datetime.strptime(time_range.start, "%Y-%m-%d")
            )
            end_time = (
                time_range.end
                if isinstance(time_range.end, datetime.date)
                else datetime.datetime.strptime(time_range.end, "%Y-%m-%d")
            )

            logger.debug(
                "determine items from %s to %s over %s...",
                start_time,
                end_time,
                bounds,
            )
            if config.search_index:
                logger.debug(
                    "use existing search index at %s", str(config.search_index)
                )
                for item in items_from_static_index(
                    bounds=bounds,
                    start_time=start_time,
                    end_time=end_time,
                    index_path=config.search_index,
                ):
                    try:
                        item_path = item.get_self_href()
                        if item_path in self.blacklist:  # pragma: no cover
                            logger.debug(
                                "item %s found in blacklist and skipping", item_path
                            )
                        elif area.intersects(shape(item.geometry)):
                            yield item
                    except GEOSException as exc:
                        raise ItemGeometryError(
                            f"item {item.get_self_href()} geometry could not be resolved: {str(exc)}"
                        )

            else:
                logger.debug("using dumb ls directory search at %s", str(self.endpoint))
                for item in items_from_directories(
                    bounds=bounds,
                    start_time=start_time,
                    end_time=end_time,
                    endpoint=self.endpoint,
                    day_subdir_schema=self.day_subdir_schema,
                    stac_json_endswith=self.stac_json_endswith,
                ):
                    item_path = item.get_self_href()
                    if item_path in self.blacklist:  # pragma: no cover
                        logger.debug(
                            "item %s found in blacklist and skipping", item_path
                        )
                    elif area.intersects(shape(item.geometry)):
                        yield item

    def _eo_bands(self) -> list:
        for collection_name in self.collections:
            for (
                collection_properties
            ) in UTMSearchConfig().sinergise_aws_collections.values():
                if collection_properties["id"] == collection_name:
                    collection = Collection.from_dict(
                        collection_properties["path"].read_json()
                    )
                    if collection:
                        summary = collection.summaries.to_dict()
                        if "eo:bands" in summary:
                            return summary["eo:bands"]
                    else:
                        raise ValueError(f"cannot find collection {collection}")
        else:
            logger.debug(
                "cannot find eo:bands definition from collections %s",
                self.collections,
            )
            return []

    def get_collections(self):
        """
        yeild transformed collection from:
            https://sentinel-s2-l2a-stac.s3.amazonaws.com/sentinel-s2-l2a.json,
            or https://sentinel-s2-l1c-stac.s3.amazonaws.com/sentinel-s2-l1c.json,
            etc.
        """
        for collection_properties in self.config.sinergise_aws_collections.values():
            collection = Collection.from_dict(collection_properties["path"].read_json())
            for collection_name in self.collections:
                if collection_name == collection.id:
                    yield collection


def items_from_static_index(
    bounds: Bounds,
    start_time: Union[datetime.datetime, datetime.date],
    end_time: Union[datetime.datetime, datetime.date],
    index_path: MPathLike,
) -> Generator[Item, None, None]:
    index_path = MPath.from_inp(index_path)

    start_time = to_datetime(start_time)
    # add day at end_time to include last day
    end_time = to_datetime(end_time + datetime.timedelta(days=1))

    # open index and determine which S2Tiles are covered
    with fiona_open(index_path) as index:
        # look at entries in every S2Tile and match with timestamp
        for s2tile_feature in index.filter(bbox=bounds):
            with fiona_open(
                index_path.parent / s2tile_feature.properties["path"]
            ) as s2tile:
                for item_feature in s2tile.filter(bbox=bounds):
                    # remove timezone info in order to compare with start_time and end_time
                    timestamp = to_datetime(
                        item_feature.properties["datetime"]
                    ).replace(tzinfo=None)

                    if start_time <= timestamp <= end_time:
                        yield Item.from_dict(
                            MPath.from_inp(item_feature.properties["path"]).read_json()
                        )


def items_from_directories(
    bounds: Bounds,
    start_time: Union[datetime.datetime, datetime.date],
    end_time: Union[datetime.datetime, datetime.date],
    endpoint: MPathLike,
    day_subdir_schema: str = "{year}/{month:02d}/{day:02d}",
    stac_json_endswith: str = "T{tile_id}.json",
) -> Generator[Item, None, None]:
    # get Sentinel-2 tiles over given bounds
    s2_tiles = s2_tiles_from_bounds(*bounds)

    # for each day within time range, look for tiles
    for day in day_range(start_date=start_time, end_date=end_time):
        day_path = MPath.from_inp(endpoint) / day_subdir_schema.format(
            year=day.year, month=day.month, day=day.day
        )
        for item in find_items(
            day_path,
            s2_tiles,
            product_endswith=stac_json_endswith,
        ):
            yield item


def find_items(
    path: MPath,
    s2_tiles: List[S2Tile],
    product_endswith: str = "T{tile_id}.json",
) -> Generator[Item, None, None]:
    match_parts = tuple(
        product_endswith.format(tile_id=s2_tile.tile_id) for s2_tile in s2_tiles
    )
    for product_path in path.ls():
        if product_path.endswith(match_parts):
            yield Item.from_file(product_path)
