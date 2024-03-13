"""
Catalogs define access to a search interface which provide products
as pystac Items.
"""

from mapchete_eo.search import STACSearchCatalog, UTMSearchCatalog


class EarthSearchV1S2L2A(STACSearchCatalog):
    """Earth-Search catalog for Sentinel-2 Level 2A COGs."""

    endpoint: str = "https://earth-search.aws.element84.com/v1/"


class AWSSearchCatalogS2L2A(UTMSearchCatalog):
    """
    Not a search endpoint, just hanging STAC collection with items separately.
    Need custom parser/browser to find scenes based on date and UTM MGRS Granule

    https://sentinel-s2-l2a-stac.s3.amazonaws.com/sentinel-s2-l2a.json
    """

    endpoint: str = "s3://sentinel-s2-l2a-stac/"


# TODO: DIAS OpenSearch: https://gitlab.eox.at/maps/mapchete_eo/-/issues/7
