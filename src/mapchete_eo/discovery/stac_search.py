import datetime
import logging
from functools import cached_property

from mapchete.io.vector import IndexedFeatures
from mapchete.tile import BufferedTilePyramid
from mapchete.validate import validate_bounds
from pystac_client import Client
from shapely.geometry import box
from tilematrix import Bounds

from mapchete_eo.discovery.base import Catalog

logger = logging.getLogger(__name__)


class STACSearchCatalog(Catalog):
    def __init__(
        self,
        baseurl: str = None,
        collection: str = None,
        bounds: Bounds = None,
        start_time: datetime.datetime = None,
        end_time: datetime.datetime = None,
        config: dict = None,
        **kwargs,
    ) -> None:
        self.bounds = bounds
        self.start_time = start_time
        self.end_time = end_time
        self.client = Client.open(baseurl)
        self.collection = collection
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
        collection = self.client.get_collection(self.collection)
        item_assets = collection.extra_fields.get("item_assets")
        out = []
        for v in item_assets.values():
            if "eo:bands" in v and "data" in v.get("roles", []):
                out.append(v["eo:bands"])
        if len(out) == 0:
            raise ValueError(
                f"cannot find eo:bands definition from collection {self.collection}"
            )
        return out

    @cached_property
    def default_search_params(self):
        return {
            "collections": [self.collection],
            "bbox": ",".join(map(str, self.bounds)),
            "datetime": f"{self.start_time}/{self.end_time}",
            "query": [f"eo:cloud_cover<{self.config['max_cloud_percent']}"],
        }

    def _search(self, **kwargs):
        search_params = dict(self.default_search_params, **kwargs)
        logger.debug(f"query catalog using params: {search_params}")
        return self.client.search(**search_params)


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
