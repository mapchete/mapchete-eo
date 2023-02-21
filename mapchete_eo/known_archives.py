"""
Archives contain data in a structured form.

Items from an archive can be found by using a Catalog and a PathMapper.

Archive:
    * Catalog
        * collection
    * Path mapper: translates from Catalog results to storage paths
        * takes a pystac.Item as input
    * Storage?: contains certain settings/options to access data

NOTE:
* COG and JP2 archives differ in that the JP2 files don't have a nodata value encoded!
class Archive():
    catalog: KnownCatalogs
    storage_options: dict = {}
"""

from enum import Enum

from mapchete_eo.known_catalogs import KnownCatalogs

# AWS L1C JP2 Archive v0:
#   * earth search v0
#   * processing level 2a
#   * E84 path mapper

# AWS L1C JP2 Archive v1:
#   * earth search v1
#   * processing level 2a
#   * E84 path mapper

# AWS L2A COG Archive v0:
#   * earth search v0
#   * processing level 2a
#   * E84 path mapper

# AWS L2A COG Archive v1:
#   * earth search v1
#   * processing level 2a
#   * E84 path mapper

# AWS L2A JP2 Archive v0:
#   * earth search v0
#   * processing level 2a
#   * E84 path mapper

# AWS L2A JP2 Archive v1:
#   * earth search v1
#   * processing level 2a
#   * E84 path mapper


class S2AWSCOGArchive:

    catalog = KnownCatalogs.earth_search_s2_cogs
    # path_mapper = TODO
    storage_options: dict = {
        "baseurl": "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/"
    }


# class S2AWSJP2Archive:

#     catalog = KnownCatalogs.sinergise_s2
#     storage_options: dict = {}


class KnownArchives(Enum):
    S2AWS_COG = S2AWSCOGArchive
    S2AWS_JP2 = S2AWSJP2Archive
