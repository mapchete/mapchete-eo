import logging
from typing import Optional, Union

import pystac

from mapchete_eo.exceptions import CorruptedProductMetadata
from mapchete_eo.io.items import get_item_property
from mapchete_eo.platforms.sentinel2.config import CacheConfig
from mapchete_eo.platforms.sentinel2.product import S2Product
from mapchete_eo.platforms.sentinel2.source import Sentinel2Source
from mapchete_eo.product import add_to_blacklist
from mapchete_eo.settings import mapchete_eo_settings

logger = logging.getLogger(__name__)


def parse_s2_product(
    item: pystac.Item,
    cache_config: Optional[CacheConfig] = None,
    cache_all: bool = False,
) -> Union[S2Product, CorruptedProductMetadata]:
    # use mapper from source if applickable
    source: Union[Sentinel2Source, None] = item.properties.pop(
        "mapchete_eo:source", None
    )
    try:
        s2product = S2Product.from_stac_item(
            item,
            cache_config=cache_config,
            cache_all=cache_all,
            metadata_mapper=None if source is None else source.get_s2metadata_mapper(),
            item_modifier_funcs=None if source is None else source.item_modifier_funcs,
            lazy_load_item=mapchete_eo_settings.lazy_load_stac_items,
            item_property_cache={
                key: get_item_property(item, key)
                for key in [
                    "datetime",
                    "eo:cloud_cover",
                    "id",
                    "s2:datastrip_id",
                ]
            },
        )
    except CorruptedProductMetadata as exc:
        add_to_blacklist(item.get_self_href())
        return exc
    return s2product
