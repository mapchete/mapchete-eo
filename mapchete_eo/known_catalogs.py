"""
Catalogs define access to a search interface which provide products
as pystac Items.
"""

from typing import List

from pystac import Item

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
    id: str = "sentinel-s2-l2a"
    description: str = "Sentinel-2 L2A JPEG2000 archive on AWS."
    stac_extensions: List[str] = []

    def standardize_item(self, item: Item) -> Item:
        """Make sure item metadata is following the standard."""

        # change 'sentinel2' prefix to 's2'
        properties = {
            k.replace("sentinel2:", "s2:"): v for k, v in item.properties.items()
        }

        # add datastrip id as 's2:datastrip_id'
        if "s2:datastrip_id" not in properties:
            from mapchete_eo.platforms.sentinel2 import S2Metadata

            s2_metadata = S2Metadata.from_stac_item(item)
            properties["s2:datastrip_id"] = s2_metadata.datastrip_id

        item.properties = properties
        return item
