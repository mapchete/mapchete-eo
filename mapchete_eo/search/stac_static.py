import datetime
import logging
import warnings
from functools import cached_property
from typing import Union

from mapchete.io.vector import IndexedFeatures, bounds_intersect
from pystac.stac_io import StacIO
from pystac_client import Client
from tilematrix import Bounds

from mapchete_eo.search.base import Catalog, FSSpecStacIO
from mapchete_eo.time import time_ranges_intersect

logger = logging.getLogger(__name__)


StacIO.set_default(FSSpecStacIO)


class STACStaticCatalog(Catalog):
    def __init__(
        self,
        baseurl: str,
        start_time: Union[datetime.datetime, None] = None,
        end_time: Union[datetime.datetime, None] = None,
        bounds: Bounds = None,
        **kwargs,
    ) -> None:
        self.client = Client.from_file(baseurl, stac_io=FSSpecStacIO())
        self.collections = [c.id for c in self.client.get_children()]
        self.bounds = bounds
        self.start_time = start_time
        self.end_time = end_time

    @cached_property
    def items(self) -> IndexedFeatures:
        def _gen_items():
            logger.debug("iterate through children")
            for item in _all_intersecting_items(
                self.client,
                bounds=self.bounds,
                timespan=(self.start_time, self.end_time),
            ):
                item.make_asset_hrefs_absolute()
                yield item

        items = list(_gen_items())
        logger.debug("%s items found", len(items))
        return IndexedFeatures(items)

    @cached_property
    def eo_bands(self) -> list:
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
            if _collection_extent_intersects(
                collection,
                bounds=self.bounds,
                timespan=(self.start_time, self.end_time),
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


def _all_intersecting_items(collection, **kwargs):
    # collection items
    logger.debug("checking items...")
    for item in collection.get_items():
        # yield item if it intersects with extent
        logger.debug(f"item {item.id}")
        if _item_extent_intersects(item, **kwargs):
            logger.debug(f"item {item.id} within search parameters")
            yield item

    # collection children
    logger.debug("checking collections...")
    for child in collection.get_children():
        # yield collection if it intersects with extent
        logger.debug(f"collection {collection.id}")
        if _collection_extent_intersects(child, **kwargs):
            logger.debug(f"found catalog {child.id} with intersecting items")
            yield from _all_intersecting_items(child, **kwargs)


def _item_extent_intersects(item, bounds=None, timespan=None):
    spatial_intersect = bounds_intersect(item.bbox, bounds) if bounds else True
    start_time, end_time = timespan
    if start_time is None and end_time is None:
        temporal_intersect = True
    else:
        temporal_intersect = time_ranges_intersect(
            [item.datetime, item.datetime], timespan
        )
    logger.debug(
        f"spatial intersect: {spatial_intersect}, temporal intersect: {temporal_intersect}"
    )
    return spatial_intersect and temporal_intersect


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
    start_time, end_time = timespan
    if start_time is None and end_time is None:
        temporal_intersect = True
    else:
        temporal_intersect = _intersects_temporally()

    logger.debug(
        f"spatial intersect: {spatial_intersect}, temporal intersect: {temporal_intersect}"
    )
    return spatial_intersect and temporal_intersect
