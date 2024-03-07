import datetime
import json
import logging
from functools import cached_property
from typing import Dict, List, Optional

import numpy as np
from mapchete.io import fiona_open
from mapchete.io.vector import IndexedFeatures
from mapchete.path import MPath, MPathLike
from mapchete.types import Bounds
from pystac.collection import Collection
from pystac.item import Item
from shapely import intersects
from shapely.geometry import Polygon, box, shape

from mapchete_eo.search.base import Catalog
from mapchete_eo.search.config import UTMSearchConfig
from mapchete_eo.types import TimeRange

logger = logging.getLogger(__name__)


class UTMSearchCatalog(Catalog):
    def __init__(
        self,
        time: TimeRange,
        endpoint: Optional[MPathLike] = None,
        collections: List[str] = [],
        bounds: Bounds = None,
        config: UTMSearchConfig = UTMSearchConfig(),
        **kwargs,
    ) -> None:
        self._collection_items: Dict = {}
        self.bounds = bounds
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
        self.client = endpoint or self.endpoint
        if len(collections) == 0:  # pragma: no cover
            raise ValueError("no collections provided")
        self.collections = collections
        self.config = config

    @cached_property
    def items(self) -> IndexedFeatures:
        """
        Collect STAC items from https://sentinel-s2-l2a-stac.s3.amazonaws.com/
        by time and granules.
        Get mgrs granules from bounds, list the date from the source endpoint/bucket and filter out the matching
        products and return them as STAC items, like with the element 84 endpoint, just without the search client.
        s3://sentinel-s2-l2a-stac/2023/06/04/S2B_OPER_MSI_L2A_TL_2BPS_20230604T235444_A032617_T01WCN.json
        """

        def daterange(start_date, end_date):
            for n in range(int((end_date - start_date).days)):
                yield start_date + datetime.timedelta(n)

        def get_utm_s2_mgrs_granules(self):
            utm_s2_mgrs_granules = []
            with fiona_open(self.config.mgrs_s2_grid) as mgrs_src:
                # see fiona filter while opening
                for f in mgrs_src:
                    if intersects(shape(f["geometry"]), box(*self.bounds)):
                        utm_s2_mgrs_granules.append(f["properties"]["MGRS"])

                    # Handle eastern Part of Antimedian, warp MGRS and process bounds by 360
                    if "01" in f["properties"]["MGRS"]:
                        x, y = shape(f["geometry"]).exterior.coords.xy
                        x += np.full(np.array(x).shape, 360)
                        f_360_offset = Polygon(list(zip(x, y)))
                        if intersects(f_360_offset, box(*self.bounds)):
                            utm_s2_mgrs_granules.append(f["properties"]["MGRS"])
            return utm_s2_mgrs_granules

        def _get_items():
            stac_items = []
            mgrs_granules_list = get_utm_s2_mgrs_granules(self)

            for single_date in daterange(
                start_date=self.start_time, end_date=self.end_time
            ):
                for mgrs in mgrs_granules_list:
                    item_path = item_path_constructor(
                        root=MPath(self.client), single_date=single_date, mgrs=mgrs
                    )
                    if item_path is None:
                        continue
                    with item_path.open() as src:
                        stac_items.append(Item.from_dict(json.loads(src.read())))
            return stac_items

        return IndexedFeatures(_get_items())

    @cached_property
    def eo_bands(self) -> list:
        for collection_name in self.collections:
            for collection_properties in self.config.sinergise_aws_collections.values():
                if collection_properties["id"] == collection_name:
                    collection = get_collection(collection_properties["path"])
                    if collection:
                        item_assets = collection.summaries.to_dict()
                        for k, v in item_assets.items():
                            if "eo:bands" in k:
                                return v
                    else:
                        raise ValueError(f"cannot find collection {collection}")
        else:
            raise ValueError("cannot find eo:bands definition from collections")

    def get_collections(self):
        """
        yeild transformed collection from:
            https://sentinel-s2-l2a-stac.s3.amazonaws.com/sentinel-s2-l2a.json,
            or https://sentinel-s2-l1c-stac.s3.amazonaws.com/sentinel-s2-l1c.json,
            etc.
        """
        for collection_properties in self.config.sinergise_aws_collections.values():
            collection = get_collection(collection_properties["path"])
            for collection_name in self.collections:
                if collection_name == collection.id:
                    yield collection


def get_collection(path):
    with path.open() as src:
        return Collection.from_dict(json.loads(src.read()))


def item_path_constructor(root, single_date, mgrs):
    date_str = single_date.strftime("%Y/%m/%d")
    out_date_path = MPath(f"{root}{date_str}/")
    out_item_path = None
    for p in out_date_path.ls():
        if mgrs in p.name:
            out_item_path = MPath(f"{str(out_date_path)}{p.name}")
    return out_item_path
