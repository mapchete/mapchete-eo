import logging
import warnings
from functools import cached_property
from typing import List, Optional, Tuple, Union

import pystac
from mapchete.io.vector import IndexedFeatures, bounds_intersect
from mapchete.path import MPathLike
from mapchete.types import BoundsLike
from pystac.stac_io import StacIO
from pystac_client import Client
from shapely.geometry import box, shape
from tilematrix import Bounds

from mapchete_eo.io.items import item_fix_footprint
from mapchete_eo.search.base import (
    CatalogProtocol,
    FSSpecStacIO,
    StaticCatalogWriterMixin,
)
from mapchete_eo.time import time_ranges_intersect
from mapchete_eo.types import DateTimeLike, TimeRange

logger = logging.getLogger(__name__)


StacIO.set_default(FSSpecStacIO)


class STACStaticCatalog(CatalogProtocol, StaticCatalogWriterMixin):
    def __init__(
        self,
        baseurl: Optional[MPathLike] = None,
        time: Optional[Union[TimeRange, List[TimeRange]]] = None,
        bounds: Optional[Bounds] = None,
        footprint_buffer: float = 0,
        **kwargs,
    ) -> None:
        self.client = Client.from_file(str(baseurl), stac_io=FSSpecStacIO())
        self.id = self.client.id
        self.description = self.client.description
        self.stac_extensions = self.client.stac_extensions
        self.collections = [c.id for c in self.client.get_children()]
        self.bounds = bounds
        self.time = time if isinstance(time, list) else [time] if time else []
        self.footprint_buffer = footprint_buffer
        self.eo_bands = self._eo_bands()

    @cached_property
    def items(self) -> IndexedFeatures:
        def _gen_items():
            if self.bounds is None:
                return
            logger.debug("iterate through children")
            for collection in self.client.get_collections():
                if self.time:
                    for time_range in self.time:
                        for item in _all_intersecting_items(
                            collection,
                            bounds=self.bounds,
                            timespan=(time_range.start, time_range.end),
                        ):
                            item.make_asset_hrefs_absolute()
                            yield item_fix_footprint(item)
                else:
                    for item in _all_intersecting_items(
                        collection,
                        bounds=self.bounds,
                    ):
                        item.make_asset_hrefs_absolute()
                        yield item_fix_footprint(item)

        items = list(_gen_items())
        logger.debug("%s items found", len(items))
        return IndexedFeatures(items)

    def _eo_bands(self) -> List[str]:
        for collection in self.client.get_children():
            eo_bands = collection.extra_fields.get("properties", {}).get("eo:bands")
            if eo_bands:
                return eo_bands
        else:
            warnings.warn(
                "Unable to read eo:bands definition from collections. "
                "Trying now to get information from assets ..."
            )

            # see if eo:bands can be found in properties
            item = _get_first_item(self.client.get_children())
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

            raise ValueError("cannot find eo:bands definition")

    def get_collections(self):
        for collection in self.client.get_children():
            for time_range in self.time:
                if _collection_extent_intersects(
                    collection,
                    bounds=self.bounds,
                    timespan=(time_range.start, time_range.end),
                ):
                    yield collection


def _get_first_item(collections):
    for collection in collections:
        for item in collection.get_all_items():
            return item
        else:
            for child in collection.get_children():
                return _get_first_item(child)
    else:
        raise ValueError("collections contain no items")


def _all_intersecting_items(
    collection: Union[pystac.Catalog, pystac.Collection], **kwargs
):
    # collection items
    logger.debug("checking items...")
    for item in collection.get_items():
        # yield item if it intersects with extent
        logger.debug("item %s", item.id)
        if _item_extent_intersects(item, **kwargs):
            logger.debug("item %s within search parameters", item.id)
            yield item

    # collection children
    logger.debug("checking collections...")
    for child in collection.get_children():
        # yield collection if it intersects with extent
        logger.debug("collection %s", collection.id)
        if _collection_extent_intersects(child, **kwargs):
            logger.debug("found catalog %s with intersecting items", child.id)
            yield from _all_intersecting_items(child, **kwargs)


def _item_extent_intersects(
    item: pystac.Item,
    bounds: Optional[BoundsLike] = None,
    timespan: Optional[Tuple[DateTimeLike, DateTimeLike]] = None,
) -> bool:
    # NOTE: bounds intersect is faster but in the current implementation cannot
    # handle item footprints going over the Antimeridian (and have been split up into
    # MultiPolygon geometries)
    # spatial_intersect = bounds_intersect(item.bbox, bounds) if bounds else True
    spatial_intersect = (
        shape(item.geometry).intersects(box(*bounds)) if bounds else True
    )
    if timespan and item.datetime:
        temporal_intersect = time_ranges_intersect(
            (item.datetime, item.datetime), timespan
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


def _collection_extent_intersects(catalog, bounds=None, timespan=None):
    """
    Collection extent items (spatial, temporal) is a list of items, e.g. list of bounds values.
    """

    def _intersects_spatially():
        for b in catalog.extent.spatial.to_dict().get("bbox", [[]]):
            if bounds_intersect(bounds, b):
                logger.debug("spatial intersect: True")
                return True
        else:
            logger.debug("spatial intersect: False")
            return False

    def _intersects_temporally():
        for t in catalog.extent.temporal.to_dict().get("interval", [[]]):
            if time_ranges_intersect(timespan, t):
                logger.debug("temporal intersect: True")
                return True
        else:
            logger.debug("temporal intersect: False")
            return False

    spatial_intersect = _intersects_spatially() if bounds else True
    if timespan:
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
