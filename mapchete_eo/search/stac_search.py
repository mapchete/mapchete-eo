import logging
from functools import cached_property
from typing import Dict, List, Optional, Set, Union

from mapchete.io.vector import IndexedFeatures
from mapchete.path import MPathLike
from mapchete.tile import BufferedTilePyramid
from mapchete.types import Bounds
from mapchete.validate import validate_bounds
from pystac_client import Client
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

from mapchete_eo.product import blacklist_products
from mapchete_eo.search.base import Catalog
from mapchete_eo.search.config import StacSearchConfig
from mapchete_eo.settings import mapchete_eo_settings
from mapchete_eo.types import TimeRange

logger = logging.getLogger(__name__)


class STACSearchCatalog(Catalog):
    endpoint: str
    blacklist: Set[str] = (
        blacklist_products(mapchete_eo_settings.blacklist)
        if mapchete_eo_settings.blacklist
        else set()
    )

    def __init__(
        self,
        collections: List[str],
        time: Union[TimeRange, List[TimeRange]],
        endpoint: Optional[MPathLike] = None,
        bounds: Optional[Bounds] = None,
        area: Optional[BaseGeometry] = None,
        config: StacSearchConfig = StacSearchConfig(),
        **kwargs,
    ) -> None:
        self._collection_items: Dict = {}

        if area:
            self.area = area
            self.bounds = None
        elif bounds:
            self.bounds = bounds
            self.area = None
        else:  # pragma: no cover
            raise ValueError("either bounds or area have to be given")

        self.time = time if isinstance(time, list) else [time]
        self.client = Client.open(endpoint or self.endpoint)

        if len(collections) == 0:  # pragma: no cover
            raise ValueError("no collections provided")

        self.collections = collections
        self.config = config

    @cached_property
    def items(self) -> IndexedFeatures:
        def _get_items():
            for time_range in self.time:
                search = self._search(time_range=time_range)
                if search.matched() > self.config.catalog_chunk_threshold:
                    spatial_chunks = bounds_chunks(
                        map(float, self.default_search_params.get("bbox").split(",")),
                        grid="geodetic",
                        zoom=self.config.catalog_chunk_zoom,
                    )
                    logger.debug(
                        "too many products (%s), query catalog in %s chunks",
                        search.matched(),
                        len(spatial_chunks),
                    )
                    searches = (self._search(bounds=chunk) for chunk in spatial_chunks)
                else:
                    searches = (search,)

                for search in searches:
                    for item in search.items():
                        item_path = item.get_self_href()
                        if item_path in self.blacklist:  # pragma: no cover
                            logger.debug(
                                "item %s found in blacklist and skipping", item_path
                            )
                        else:
                            yield item

        return IndexedFeatures(_get_items())

    @cached_property
    def eo_bands(self) -> list:
        for collection_name in self.collections:
            collection = self.client.get_collection(collection_name)
            if collection:
                item_assets = collection.extra_fields.get("item_assets", {})
                for v in item_assets.values():
                    if "eo:bands" in v and "data" in v.get("roles", []):
                        return ["eo:bands"]
            else:  # pragma: no cover
                raise ValueError(f"cannot find collection {collection}")
        else:  # pragma: no cover
            raise ValueError("cannot find eo:bands definition from collections")

    @cached_property
    def default_search_params(self):
        return {
            "collections": self.collections,
            "bbox": ",".join(map(str, self.bounds)) if self.bounds else None,
            "intersects": self.area if self.area else None,
            "query": [f"eo:cloud_cover<{self.config.max_cloud_percent}"],
        }

    def _search(self, time_range=None, **kwargs):
        if time_range is None:  # pragma: no cover
            raise ValueError("time_range not provided")
        search_params = dict(
            self.default_search_params,
            datetime=f"{time_range.start}/{time_range.end}",
            **kwargs,
        )
        logger.debug("query catalog using params: %s", search_params)
        return self.client.search(**search_params)

    def get_collections(self):
        for collection_name in self.collections:
            yield self.client.get_collection(collection_name)


def bounds_intersection(bounds1, bounds2):
    g = box(*bounds1).intersection(box(*bounds2))
    if g.is_empty:
        raise ValueError(f"bounds must have an intersecting area: {bounds1}, {bounds2}")
    return Bounds(*g.bounds)


def bounds_chunks(bounds, grid="geodetic", zoom=5):
    tile_pyramid = BufferedTilePyramid(grid)
    bounds = validate_bounds(bounds)
    # if bounds cross the antimeridian, snap them to CRS bouds
    if bounds.left < tile_pyramid.left:
        logger.warning("snap left bounds value back to CRS bounds")
        bounds = Bounds(tile_pyramid.left, bounds.bottom, bounds.right, bounds.top)
    if bounds.right > tile_pyramid.right:
        logger.warning("snap right bounds value back to CRS bounds")
        bounds = Bounds(bounds.left, bounds.bottom, tile_pyramid.right, bounds.top)
    return [
        bounds_intersection(tile.bounds, bounds)
        for tile in tile_pyramid.tiles_from_bounds(bounds, zoom=zoom)
    ]
