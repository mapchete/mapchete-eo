from functools import cached_property
import logging
import warnings
from typing import Any, Dict, Generator, List, Optional, Union

from mapchete import Bounds
from mapchete.types import BoundsLike
from pystac import Item, Catalog, Collection
from mapchete.io.vector import bounds_intersect
from pystac.stac_io import StacIO
from pystac_client import CollectionClient
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from mapchete_eo.search.base import (
    CollectionSearcher,
    FSSpecStacIO,
    StaticCollectionWriterMixin,
    filter_items,
)
from mapchete_eo.search.config import StacStaticConfig
from mapchete_eo.time import time_ranges_intersect
from mapchete_eo.types import TimeRange

logger = logging.getLogger(__name__)


StacIO.set_default(FSSpecStacIO)


class STACStaticCollection(StaticCollectionWriterMixin, CollectionSearcher):
    config_cls = StacStaticConfig

    @cached_property
    def client(self) -> CollectionClient:
        return CollectionClient.from_file(str(self.collection), stac_io=FSSpecStacIO())

    @cached_property
    def eo_bands(self) -> List[str]:
        eo_bands = self.client.extra_fields.get("properties", {}).get("eo:bands")
        if eo_bands:
            return eo_bands
        else:
            warnings.warn(
                "Unable to read eo:bands definition from collection. "
                "Trying now to get information from assets ..."
            )
            # see if eo:bands can be found in properties
            try:
                item = next(self.client.get_items(recursive=True))
                eo_bands = item.properties.get("eo:bands")
                if eo_bands:
                    return eo_bands

                # look through the assets and collect eo:bands
                out = {}
                for asset in item.assets.values():
                    for eo_band in asset.extra_fields.get("eo:bands", []):
                        out[eo_band["name"]] = eo_band
                if out:
                    return [v for v in out.values()]
            except StopIteration:
                pass

            logger.debug("cannot find eo:bands definition")
            return []

    def search(
        self,
        time: Optional[Union[TimeRange, List[TimeRange]]] = None,
        bounds: Optional[BoundsLike] = None,
        area: Optional[BaseGeometry] = None,
        query: Optional[str] = None,
        search_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Generator[Item, None, None]:
        if area is None and bounds:
            bounds = Bounds.from_inp(bounds)
            area = shape(bounds)
        for item in filter_items(self._raw_search(time=time, area=area), query=query):
            yield item

    def _raw_search(
        self,
        time: Optional[Union[TimeRange, List[TimeRange]]] = None,
        area: Optional[BaseGeometry] = None,
    ) -> Generator[Item, None, None]:
        if area is not None and area.is_empty:
            return
        logger.debug("iterate through children")
        if time:
            for time_range in time if isinstance(time, list) else [time]:
                for item in _all_intersecting_items(
                    self.client,
                    area=area,
                    time_range=time_range,
                ):
                    item.make_asset_hrefs_absolute()
                    yield item
        else:
            for item in _all_intersecting_items(
                self.client,
                area=area,
            ):
                item.make_asset_hrefs_absolute()
                yield item


def _all_intersecting_items(
    collection: Union[Catalog, Collection],
    area: BaseGeometry,
    time_range: Optional[TimeRange] = None,
):
    # collection items
    logger.debug("checking items...")
    for item in collection.get_items():
        # yield item if it intersects with extent
        logger.debug("item %s", item.id)
        if _item_extent_intersects(item, area=area, time_range=time_range):
            logger.debug("item %s within search parameters", item.id)
            yield item

    # collection children
    logger.debug("checking collections...")
    for child in collection.get_children():
        # yield collection if it intersects with extent
        logger.debug("collection %s", collection.id)
        if _collection_extent_intersects(child, area=area, time_range=time_range):
            logger.debug("found catalog %s with intersecting items", child.id)
            yield from _all_intersecting_items(child, area=area, time_range=time_range)


def _item_extent_intersects(
    item: Item,
    area: Optional[BaseGeometry] = None,
    time_range: Optional[TimeRange] = None,
) -> bool:
    # NOTE: bounds intersect is faster but in the current implementation cannot
    # handle item footprints going over the Antimeridian (and have been split up into
    # MultiPolygon geometries)
    # spatial_intersect = bounds_intersect(item.bbox, bounds) if bounds else True
    spatial_intersect = shape(item.geometry).intersects(area) if area else True
    if time_range and item.datetime:
        temporal_intersect = time_ranges_intersect(
            (item.datetime, item.datetime), (time_range.start, time_range.end)
        )
        logger.debug(
            "spatial intersect: %s, temporal intersect: %s",
            spatial_intersect,
            temporal_intersect,
        )
        return spatial_intersect and temporal_intersect
    else:
        logger.debug("spatial intersect: %s", spatial_intersect)
        return spatial_intersect


def _collection_extent_intersects(
    catalog, area: Optional[BaseGeometry] = None, time_range: Optional[TimeRange] = None
):
    """
    Collection extent items (spatial, temporal) is a list of items, e.g. list of bounds values.
    """

    def _intersects_spatially():
        for b in catalog.extent.spatial.to_dict().get("bbox", [[]]):
            if bounds_intersect(area.bounds, b):
                logger.debug("spatial intersect: True")
                return True
        else:
            logger.debug("spatial intersect: False")
            return False

    def _intersects_temporally():
        for t in catalog.extent.temporal.to_dict().get("interval", [[]]):
            if time_ranges_intersect((time_range.start, time_range.end), t):
                logger.debug("temporal intersect: True")
                return True
        else:
            logger.debug("temporal intersect: False")
            return False

    spatial_intersect = _intersects_spatially() if area else True
    if time_range:
        temporal_intersect = _intersects_temporally()
        logger.debug(
            "spatial intersect: %s, temporal intersect: %s",
            spatial_intersect,
            temporal_intersect,
        )
        return spatial_intersect and temporal_intersect
    else:
        logger.debug("spatial intersect: %s", spatial_intersect)
        return spatial_intersect
