import logging

import pystac

from mapchete_eo.platforms.sentinel2.base import S2Product

# from mapchete_eo.platforms.sentinel2.config import CacheConfig


logger = logging.getLogger(__name__)


# def s2product_from_item(item: pystac.Item, cache_config: CacheConfig) -> S2Product:
def s2product_from_item(item: pystac.Item, cache_config) -> S2Product:
    logger.debug("parse STAC item %s", item)
    s2product = S2Product(item, cache_config=cache_config)

    # cache assets if configured
    s2product.cache_assets()

    # cache BRDF grids if configured
    s2product.cache_brdf_grids()

    return s2product
