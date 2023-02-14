from enum import Enum

from mapchete_eo.known_catalogs import KnownCatalogs

# NOTE:
#
# * COG and JP2 archives differ in that the JP2 files don't have a nodata value encoded!


# class Archive():
#     catalog: KnownCatalogs
#     storage_options: dict = {}


class S2AWSCOGArchive:

    catalog = KnownCatalogs.earth_search_s2_cogs
    storage_options: dict = {
        "baseurl": "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/"
    }


class S2AWSJP2Archive:

    catalog = KnownCatalogs.sinergise_s2
    storage_options: dict = {}


class KnownArchives(Enum):
    S2AWS_COG = S2AWSCOGArchive
    S2AWS_JP2 = S2AWSJP2Archive
