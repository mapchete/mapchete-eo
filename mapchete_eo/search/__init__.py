"""
A catalog is an instance with a specific endpoint and a specific collection.

The catalog class aims to abstract product search as well as homogenization
of product metadata.

It helps the InputData class to find the input products and their metadata.
"""

from mapchete_eo.search.stac_search import STACSearchCatalog
from mapchete_eo.search.stac_static import STACStaticCatalog
from mapchete_eo.search.utm_search import UTMSearchCatalog

__all__ = ["STACSearchCatalog", "STACStaticCatalog", "UTMSearchCatalog"]
