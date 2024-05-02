import datetime
import logging
from functools import cached_property
from typing import Dict, Generator, List, Optional

from mapchete.io.vector import IndexedFeatures
from mapchete.path import MPath, MPathLike
from mapchete.types import Bounds
from pystac.collection import Collection
from pystac.item import Item
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from mapchete_eo.io.items import item_fix_footprint
from mapchete_eo.search.base import CatalogProtocol, StaticCatalogWriterMixin
from mapchete_eo.search.config import UTMSearchConfig
from mapchete_eo.search.s2_mgrs import S2Tile, s2_tiles_from_bounds
from mapchete_eo.time import day_range
from mapchete_eo.types import TimeRange

logger = logging.getLogger(__name__)


class UTMSearchCatalog(CatalogProtocol, StaticCatalogWriterMixin):
    endpoint: str

    def __init__(
        self,
        time: TimeRange,
        endpoint: Optional[MPathLike] = None,
        collections: List[str] = [],
        bounds: Bounds = None,
        area: Optional[BaseGeometry] = None,
        config: UTMSearchConfig = UTMSearchConfig(),
        **kwargs,
    ) -> None:
        if area is not None:
            self.area = area
            self.bounds = Bounds.from_inp(self.area)
        elif bounds is not None:
            self.bounds = Bounds.from_inp(bounds)
            self.area = shape(self.bounds)
        else:  # pragma: no cover
            raise ValueError("either bounds or area have to be given")

        self._collection_items: Dict = {}
        self.time = time if isinstance(time, list) else [time]
        self.start_time = (
            time.start
            if isinstance(time.start, datetime.date)
            else datetime.datetime.strptime(time.start, "%Y-%m-%d")
        )
        self.end_time = (
            time.end
            if isinstance(time.end, datetime.date)
            else datetime.datetime.strptime(time.end, "%Y-%m-%d")
        )
        self.endpoint = endpoint or self.endpoint
        if len(collections) == 0:  # pragma: no cover
            raise ValueError("no collections provided")
        self.collections = collections
        self.config = config
        self.eo_bands = self._eo_bands()

    @cached_property
    def items(self) -> IndexedFeatures:
        """
        Collect STAC items from https://sentinel-s2-l2a-stac.s3.amazonaws.com/
        by time and granules.
        Get mgrs granules from bounds, list the date from the source endpoint/bucket and filter out the matching
        products and return them as STAC items, like with the element 84 endpoint, just without the search client.
        s3://sentinel-s2-l2a-stac/2023/06/04/S2B_OPER_MSI_L2A_TL_2BPS_20230604T235444_A032617_T01WCN.json
        """
        logger.debug(
            "determine items from %s to %s over %s...",
            self.start_time,
            self.end_time,
            self.bounds,
        )

        def _get_items():
            for item in items_from_directories(
                bounds=self.bounds,
                start_time=self.start_time,
                end_time=self.end_time,
                endpoint=self.endpoint,
            ):
                if self.area.intersects(shape(item.geometry)):
                    yield self.standardize_item(item)

        if (self.area is not None and self.area.is_empty) or self.bounds is None:
            return IndexedFeatures([])
        return IndexedFeatures(_get_items())

    def _eo_bands(self) -> list:
        for collection_name in self.collections:
            for collection_properties in self.config.sinergise_aws_collections.values():
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
            raise ValueError(
                f"cannot find eo:bands definition from collections {self.collections}"
            )

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


def items_from_directories(
    bounds: Bounds,
    start_time: datetime.datetime,
    end_time: datetime.datetime,
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
            yield item_fix_footprint(item)


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
