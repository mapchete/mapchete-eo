from __future__ import annotations

import logging
from datetime import datetime
from functools import cached_property
from typing import Any, Dict, Generator, Iterator, List, Optional, Union

from mapchete import Timer
from mapchete.tile import BufferedTilePyramid
from mapchete.types import Bounds, BoundsLike
from pystac import Item
from pystac_client import Client, CollectionClient, ItemSearch
from shapely.geometry import shape, box
from shapely.geometry.base import BaseGeometry

from mapchete_eo.search.base import CollectionSearcher, StaticCollectionWriterMixin
from mapchete_eo.search.config import StacSearchConfig, patch_invalid_assets
from mapchete_eo.types import TimeRange

logger = logging.getLogger(__name__)


class STACSearchCollection(StaticCollectionWriterMixin, CollectionSearcher):
    collection: str
    config_cls = StacSearchConfig

    @cached_property
    def client(self) -> CollectionClient:
        return CollectionClient.from_file(self.collection)

    @cached_property
    def eo_bands(self) -> List[str]:
        item_assets = self.client.extra_fields.get("item_assets", {})
        for v in item_assets.values():
            if "eo:bands" in v and "data" in v.get("roles", []):
                return ["eo:bands"]
        else:  # pragma: no cover
            logger.debug("cannot find eo:bands definition from collections")
            return []

    def search(
        self,
        time: Optional[Union[TimeRange, List[TimeRange]]] = None,
        bounds: Optional[BoundsLike] = None,
        area: Optional[BaseGeometry] = None,
        query: Optional[str] = None,
        search_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Generator[Item, None, None]:
        config = self.config_cls(**search_kwargs or {})
        if bounds:
            bounds = Bounds.from_inp(bounds)
        if area is None and bounds is None:  # pragma: no cover
            raise ValueError("either bounds or area have to be given")

        if area is not None and area.is_empty:  # pragma: no cover
            return

        def _searches() -> Generator[ItemSearch, None, None]:
            def _search_chunks(
                time_range: Optional[TimeRange] = None,
                bounds: Optional[BoundsLike] = None,
                area: Optional[BaseGeometry] = None,
                query: Optional[str] = None,
            ):
                search = self._search(
                    time_range=time_range,
                    bounds=bounds,
                    area=box(*area.bounds) if area else None,
                    query=query,
                    config=config,
                )
                logger.debug("found %s products", search.matched())
                matched = search.matched() or 0
                if matched > config.catalog_chunk_threshold:  # pragma: no cover
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
                                query=query,
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

            if time:
                # search time range(s)
                for time_range in time if isinstance(time, list) else [time]:
                    yield from _search_chunks(
                        time_range=time_range,
                        bounds=bounds,
                        area=area,
                        query=query,
                    )
            else:
                # don't apply temporal filter
                yield from _search_chunks(
                    bounds=bounds,
                    area=area,
                    query=query,
                )

        with patch_invalid_assets():
            for search in _searches():
                for item in search.items():
                    if item.get_self_href() in self.blacklist:  # pragma: no cover
                        logger.debug(
                            "item %s found in blacklist and skipping",
                            item.get_self_href(),
                        )
                        continue
                    yield item

    @cached_property
    def default_search_params(self):
        return {
            "collections": [self.client],
            "bbox": None,
            "intersects": None,
        }

    @cached_property
    def search_client(self) -> Client:
        # looks weird, right?
        #
        # one would assume that directly returning self.client.get_root() would
        # do the same but if we do so, it seems to ignore the "collections" parameter
        # and thus query all collection available on that search endpoint.
        #
        # the only way to fix this, is to instantiate Client from scratch.
        return Client.from_file(self.client.get_root().self_href)

    def _search(
        self,
        time_range: Optional[TimeRange] = None,
        bounds: Optional[Bounds] = None,
        area: Optional[BaseGeometry] = None,
        query: Optional[str] = None,
        config: StacSearchConfig = StacSearchConfig(),
        **kwargs,
    ) -> ItemSearch:
        if bounds is not None:
            if shape(bounds).is_empty:  # pragma: no cover
                raise ValueError("bounds empty")
            kwargs.update(bbox=",".join(map(str, bounds)))
        elif area is not None:
            if area.is_empty:  # pragma: no cover
                raise ValueError("area empty")
            kwargs.update(intersects=area)

        if time_range:
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
                query=[query] if query else None,
                **kwargs,
            )
        else:
            search_params = dict(
                self.default_search_params,
                query=[query] if query else None,
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
            result = self.search_client.search(
                **search_params, limit=config.catalog_pagesize
            )
        logger.debug("query took %s", str(duration))
        return result


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
