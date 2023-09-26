from collections import defaultdict
from typing import Dict, List

from mapchete_eo.protocols import EOProductProtocol


def group_products_per_property(
    products: List[EOProductProtocol], property: str
) -> Dict:
    """Group products per given property."""
    out = defaultdict(list)
    for product in products:
        out[product.get_property(property)].append(product)
    return out
