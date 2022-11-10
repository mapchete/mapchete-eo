from enum import Enum

from mapchete_eo.search import STACSearchCatalog


class E84Sentinel2COGs(STACSearchCatalog):
    COLLECTION = "sentinel-s2-l2a-cogs"
    ENDPOINT = "https://earth-search.aws.element84.com/v0/"


class SinergiseSentinel2:
    pass


class KnownCatalogs(Enum):
    earth_search_s2_cogs = E84Sentinel2COGs
    sinergise_s2 = SinergiseSentinel2
