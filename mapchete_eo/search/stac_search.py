import logging
from datetime import datetime
from functools import cached_property
from typing import Dict, Iterator, List, Optional, Set, Union

from mapchete.io.vector import IndexedFeatures
from mapchete.path import MPathLike
from mapchete.tile import BufferedTilePyramid
from mapchete.types import Bounds, BoundsLike
from pystac_client import Client
from shapely.errors import GEOSException
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from mapchete_eo.exceptions import ItemGeometryError
from mapchete_eo.io.items import item_fix_footprint
from mapchete_eo.product import blacklist_products
from mapchete_eo.search.base import CatalogProtocol, StaticCatalogWriterMixin
from mapchete_eo.search.config import StacSearchConfig
from mapchete_eo.settings import mapchete_eo_settings
from mapchete_eo.types import TimeRange

logger = logging.getLogger(__name__)


class STACSearchCatalog(CatalogProtocol, StaticCatalogWriterMixin):
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
        if area is not None:
            self.area = area
            self.bounds = None
        elif bounds is not None:
            self.bounds = bounds
            self.area = None
        else:  # pragma: no cover
            raise ValueError("either bounds or area have to be given")

        if len(collections) == 0:  # pragma: no cover
            raise ValueError("no collections provided")

        self.time = time if isinstance(time, list) else [time]
        self.client = Client.open(endpoint or self.endpoint)
        self.id = self.client.id
        self.description = self.client.description
        self.stac_extensions = self.client.stac_extensions

        self.collections = collections
        self.config = config

        self._collection_items: Dict = {}
        self.eo_bands = self._eo_bands()

    @cached_property
    def items(self) -> IndexedFeatures:
        def _get_items():
            for time_range in self.time:
                search = self._search(time_range=time_range)
                if search.matched() > self.config.catalog_chunk_threshold:
                    spatial_search_chunks = SpatialSearchChunks(
                        bounds=self.bounds,
                        area=self.area,
                        grid="geodetic",
                        zoom=self.config.catalog_chunk_zoom,
                    )
                    logger.debug(
                        "too many products (%s), query catalog in %s chunks",
                        search.matched(),
                        len(spatial_search_chunks),
                    )
                    searches = (
                        self._search(**chunk_kwargs)
                        for chunk_kwargs in spatial_search_chunks
                    )
                else:
                    searches = (search,)

                for search in searches:
                    for item in search.items():
                        try:
                            item_path = item.get_self_href()
                            if item_path in self.blacklist:  # pragma: no cover
                                logger.debug(
                                    "item %s found in blacklist and skipping", item_path
                                )
                            else:
                                yield item_fix_footprint(item)
                        except GEOSException as exc:
                            raise ItemGeometryError(
                                f"item {item.get_self_href()} geometry could not be resolved: {str(exc)}"
                            )

        if self.area is not None and self.area.is_empty:
            return IndexedFeatures([])
        return IndexedFeatures(_get_items())

    def _eo_bands(self) -> List[str]:
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

    def _search(
        self,
        time_range: Optional[TimeRange] = None,
        bounds: Optional[Bounds] = None,
        area: Optional[BaseGeometry] = None,
        **kwargs,
    ):
        if time_range is None:  # pragma: no cover
            raise ValueError("time_range not provided")

        if bounds is not None:
            if shape(bounds).is_empty:  # pragma: no cover
                raise ValueError("bounds empty")
            kwargs.update(bbox=",".join(map(str, bounds)))
        elif area is not None:
            if self.area.is_empty:  # pragma: no cover
                raise ValueError("area empty")
            kwargs.update(intersects=self.area)

        start = (
            time_range.start.date()
            if isinstance(time_range.start, datetime)
            else time_range.start
        )
        end = (
            time_range.end.date()
            if isinstance(time_range.end, datetime)
            else time_range.end
        )
        search_params = dict(
            self.default_search_params,
            datetime=f"{start}/{end}",
            **kwargs,
        )
        logger.debug("query catalog using params: %s", search_params)
        return self.client.search(**search_params)

    def get_collections(self):
        for collection_name in self.collections:
            yield self.client.get_collection(collection_name)


class SpatialSearchChunks:
    bounds: Bounds
    area: BaseGeometry
    search_kw: str
    tile_pyramid: BufferedTilePyramid
    zoom: int

    def __init__(
        self,
        bounds: Optional[BoundsLike] = None,
        area: Optional[BaseGeometry] = None,
        zoom: int = 6,
        grid: str = "geodetic",
    ):
        if bounds is not None:
            self.bounds = Bounds.from_inp(bounds)
            self.area = None
            self.search_kw = "bbox"
        elif area is not None:
            self.bounds = None
            self.area = area
            self.search_kw = "intersects"
        else:  # pragma: no cover
            raise ValueError("either area or bounds have to be given")
        self.zoom = zoom
        self.tile_pyramid = BufferedTilePyramid(grid)

    @cached_property
    def _chunks(self) -> List[Union[Bounds, BaseGeometry]]:
        if self.bounds is not None:
            bounds = self.bounds
            # if bounds cross the antimeridian, snap them to CRS bouds
            if self.bounds.left < self.tile_pyramid.left:
                logger.warning("snap left bounds value back to CRS bounds")
                bounds = Bounds(
                    self.tile_pyramid.left,
                    self.bounds.bottom,
                    self.bounds.right,
                    self.bounds.top,
                )
            if self.bounds.right > self.tile_pyramid.right:
                logger.warning("snap right bounds value back to CRS bounds")
                bounds = Bounds(
                    self.bounds.left,
                    self.bounds.bottom,
                    self.tile_pyramid.right,
                    self.bounds.top,
                )
            return [
                Bounds.from_inp(tile.bbox.intersection(shape(bounds)))
                for tile in self.tile_pyramid.tiles_from_bounds(bounds, zoom=self.zoom)
            ]
        else:
            return [
                tile.bbox.intersection(self.area)
                for tile in self.tile_pyramid.tiles_from_geom(self.area, zoom=self.zoom)
            ]

    def __len__(self) -> int:
        return len(self._chunks)

    def __iter__(self) -> Iterator[dict]:
        return iter([{self.search_kw: chunk} for chunk in self._chunks])
