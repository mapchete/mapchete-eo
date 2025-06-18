"""
Catalogs define access to a search interface which provide products
as pystac Items.
"""

from typing import List

from mapchete_eo.search import STACSearchCatalog, UTMSearchCatalog


class EarthSearchV1S2L2A(STACSearchCatalog):
    """Earth-Search catalog for Sentinel-2 Level 2A COGs."""

    endpoint: str = "https://earth-search.aws.element84.com/v1/"


class CDSESearch(STACSearchCatalog):
    """Copernicus Data Space Ecosystem (CDSE) STAC API."""

    endpoint: str = "https://stac.dataspace.copernicus.eu/v1"


class PlanetaryComputerSearch(STACSearchCatalog):
    """Planetary Computer Search."""

    endpoint: str = "https://planetarycomputer.microsoft.com/api/stac/v1/"


class AWSSearchCatalogS2L2A(UTMSearchCatalog):
    """
    Not a search endpoint, just hanging STAC collection with items separately.
    Need custom parser/browser to find scenes based on date and UTM MGRS Granule

    https://sentinel-s2-l2a-stac.s3.amazonaws.com/sentinel-s2-l2a.json
    """

    id: str = "sentinel-s2-l2a"
    endpoint: str = "s3://sentinel-s2-l2a-stac/"
    day_subdir_schema: str = "{year}/{month:02d}/{day:02d}"
    stac_json_endswith: str = "T{tile_id}.json"
    description: str = "Sentinel-2 L2A JPEG2000 archive on AWS."
    stac_extensions: List[str] = []
