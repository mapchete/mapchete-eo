import logging
from datetime import datetime
from functools import cached_property
from typing import Any, Callable, Dict, Generator, Iterator, List, Optional, Set, Union

from mapchete import Timer
from mapchete.path import MPathLike
from mapchete.tile import BufferedTilePyramid
from mapchete.types import Bounds, BoundsLike
from pystac import Item
from pystac_client import Client
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from mapchete_eo.product import blacklist_products
from mapchete_eo.search.base import CatalogSearcher, StaticCatalogWriterMixin
from mapchete_eo.search.config import StacSearchConfig
from mapchete_eo.settings import mapchete_eo_settings
from mapchete_eo.types import TimeRange

logger = logging.getLogger(__name__)


class STACSearchCatalog(StaticCatalogWriterMixin, CatalogSearcher):
    endpoint: str
    blacklist: Set[str] = (
        blacklist_products(mapchete_eo_settings.blacklist)
        if mapchete_eo_settings.blacklist
        else set()
    )
    config_cls = StacSearchConfig

    def __init__(
        self,
        collections: Optional[List[str]] = None,
        stac_item_modifiers: Optional[List[Callable[[Item], Item]]] = None,
        endpoint: Optional[MPathLike] = None,
    ):
        if collections:
            self.collections = collections
        else:  # pragma: no cover
            raise ValueError("collections must be given")
        self.client = Client.open(endpoint or self.endpoint)
        self.id = self.client.id
        self.description = self.client.description
        self.stac_extensions = self.client.stac_extensions
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
        if time is None:  # pragma: no cover
            raise ValueError("time must be set")
        if area is None and bounds is None:  # pragma: no cover
            raise ValueError("either bounds or area have to be given")

        if area is not None and area.is_empty:  # pragma: no cover
            return

        def _searches():
            for time_range in time if isinstance(time, list) else [time]:
                search = self._search(
                    time_range=time_range, bounds=bounds, area=area, config=config
                )
                logger.debug("found %s products", search.matched())
                matched = search.matched() or 0
                if matched > config.catalog_chunk_threshold:
                    spatial_search_chunks = SpatialSearchChunks(
                        bounds=bounds,
                        area=area,
                        grid="geodetic",
                        zoom=config.catalog_chunk_zoom,
                    )
                    logger.debug(
                        "too many products (%s), query catalog in %s chunks",
                        matched,
                        len(spatial_search_chunks),
                    )
                    for counter, chunk_kwargs in enumerate(spatial_search_chunks, 1):
                        with Timer() as duration:
                            chunk_search = self._search(
                                time_range=time_range,
                                config=config,
                                **chunk_kwargs,
                            )
                            yield chunk_search
                        logger.debug(
                            "returned chunk %s/%s (%s items) in %s",
                            counter,
                            len(spatial_search_chunks),
                            chunk_search.matched(),
                            duration,
                        )
                else:
                    yield search

        for search in _searches():
            for count, item in enumerate(search.items(), 1):
                item_path = item.get_self_href()
                # logger.debug("item %s/%s ...", count, search.matched())
                if item_path in self.blacklist:  # pragma: no cover
                    logger.debug("item %s found in blacklist and skipping", item_path)
                else:
                    yield item

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
            logger.debug("cannot find eo:bands definition from collections")
            return []

    @cached_property
    def default_search_params(self):
        return {
            "collections": self.collections,
            "bbox": None,
            "intersects": None,
        }

    def _search(
        self,
        time_range: Optional[TimeRange] = None,
        bounds: Optional[Bounds] = None,
        area: Optional[BaseGeometry] = None,
        config: StacSearchConfig = StacSearchConfig(),
        **kwargs,
    ):
        if time_range is None:  # pragma: no cover
            raise ValueError("time_range not provided")

        if bounds is not None:
            if shape(bounds).is_empty:  # pragma: no cover
                raise ValueError("bounds empty")
            kwargs.update(bbox=",".join(map(str, bounds)))
        elif area is not None:
            if area.is_empty:  # pragma: no cover
                raise ValueError("area empty")
            kwargs.update(intersects=area)

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
            query=[f"eo:cloud_cover<={config.max_cloud_cover}"],
            **kwargs,
        )
        if (
            bounds is None
            and area is None
            and kwargs.get("bbox", kwargs.get("intersects")) is None
        ):  # pragma: no cover
            raise ValueError("no bounds or area given")
        logger.debug("query catalog using params: %s", search_params)
        with Timer() as duration:
            result = self.client.search(**search_params, limit=config.catalog_pagesize)
        logger.debug("query took %s", str(duration))
        return result

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
                list(Bounds.from_inp(tile.bbox.intersection(shape(bounds))))
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
