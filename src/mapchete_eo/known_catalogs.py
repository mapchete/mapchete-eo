from mapchete_eo.search import STACSearchCatalog


class E84Sentinel2COGs(STACSearchCatalog):
    COLLECTION = "sentinel-s2-l2a-cogs"
    ENDPOINT = "https://earth-search.aws.element84.com/v0/"


class SinergiseSentinel2:
    pass


CATALOGS = {
    "E84Sentinel2COGs": E84Sentinel2COGs,
    "SinergiseSentinel2": SinergiseSentinel2,
}
