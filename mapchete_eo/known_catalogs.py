"""
Catalogs define access to a search interface which provide products
as pystac Items.
"""


from mapchete_eo.search import STACSearchCatalog


class EarthSearchV1S2L2A(STACSearchCatalog):
    """Earth-Search catalog for Sentinel-2 Level 2A COGs."""

    endpoint: str = "https://earth-search.aws.element84.com/v1/"


# TODO: DIAS OpenSearch: https://gitlab.eox.at/maps/mapchete_eo/-/issues/7
