import datetime
import logging
from functools import cached_property
from typing import Union, Dict, List

from mapchete.io.vector import IndexedFeatures
from mapchete.tile import BufferedTilePyramid
from mapchete.validate import validate_bounds
from pystac_client import Client
from shapely.geometry import box
from tilematrix import Bounds

from mapchete_eo.search.base import Catalog

logger = logging.getLogger(__name__)


class STACSearchCatalog(Catalog):
    ENDPOINT: str
    COLLECTION: str

    def __init__(
        self,
        endpoint: Union[str, None] = None,
        start_time: Union[datetime.date, datetime.datetime, None] = None,
        end_time: Union[datetime.date, datetime.datetime, None] = None,
        collections: List[str] = [],
        bounds: Bounds = None,
        config: dict = dict(),
        **kwargs,
    ) -> None:
        self._collection_items: Dict = {}
        self.bounds = bounds
        self.start_time = start_time
        self.end_time = end_time
        self.client = Client.open(endpoint or self.ENDPOINT)
        self.collections = collections or [self.COLLECTION]
        self.config = dict(
            max_cloud_percent=100.0,
            stac_catalog_chunk_threshold=10000,
            stac_catalog_chunk_zoom=5,
        )

    @cached_property
    def items(self) -> IndexedFeatures:
        def _get_items():
            search = self._search()
            if search.matched() > self.config["stac_catalog_chunk_threshold"]:
                spatial_chunks = bounds_chunks(
                    map(float, self.default_search_params.get("bbox").split(",")),
                    grid="geodetic",
                    zoom=self.config["stac_catalog_chunk_zoom"],
                )
                logger.debug(
                    "too many products (%s), query catalog in %s chunks",
                    search.matched(),
                    len(spatial_chunks),
                )
                searches = (self._search(bounds=chunk) for chunk in spatial_chunks)
            else:
                searches = [search]

            for search in searches:
                yield from search.get_items()

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
            else:
                raise ValueError(f"cannot fin collection {collection}")
        else:
            raise ValueError("cannot find eo:bands definition from collections")

    @cached_property
    def default_search_params(self):
        return {
            "collections": self.collections,
            "bbox": ",".join(map(str, self.bounds)),
            "datetime": f"{self.start_time}/{self.end_time}",
            "query": [f"eo:cloud_cover<{self.config['max_cloud_percent']}"],
        }

    def _search(self, **kwargs):
        search_params = dict(self.default_search_params, **kwargs)
        logger.debug(f"query catalog using params: {search_params}")
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
