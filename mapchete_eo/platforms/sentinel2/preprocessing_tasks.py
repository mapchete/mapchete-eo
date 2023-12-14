import logging
from typing import Optional, Union

import pystac

from mapchete_eo.exceptions import CorruptedProductMetadata
from mapchete_eo.platforms.sentinel2.config import CacheConfig
from mapchete_eo.platforms.sentinel2.product import S2Product
from mapchete_eo.product import add_to_blacklist
from mapchete_eo.settings import mapchete_eo_settings

logger = logging.getLogger(__name__)


def parse_s2_product(
    item: pystac.Item,
    cache_config: Optional[CacheConfig] = None,
    cache_all: bool = False,
) -> Union[S2Product, CorruptedProductMetadata]:
    try:
        s2product = S2Product.from_stac_item(
            item, cache_config=cache_config, cache_all=cache_all
        )
    except CorruptedProductMetadata as exc:
        if mapchete_eo_settings.blacklist:
            item_path = item.get_self_href()
            logger.debug("add item path %s to blacklist", item_path)
            add_to_blacklist(item_path)
        return exc
    return s2product
