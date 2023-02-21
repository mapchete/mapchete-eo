"""
Catalogs define access to a search interface which provide products
as pystac Items.
"""

from enum import Enum

from mapchete_eo.search import STACSearchCatalog


class EarthSearchV1S2L2A(STACSearchCatalog):
    # COLLECTION: str = "sentinel-2-l2a"
    endpoint: str = "https://earth-search.aws.element84.com/v1/"


# E84 v0 for testing mainly
class EarthSearchV0S2L2A(STACSearchCatalog):
    # COLLECTION: str = "sentinel-s2-l2a-cogs"
    endpoint: str = "https://earth-search.aws.element84.com/v0/"


# TODO: DIAS OpenSearch: https://gitlab.eox.at/maps/mapchete_eo/-/issues/7
