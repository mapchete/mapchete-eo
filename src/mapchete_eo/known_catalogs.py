from mapchete_eo.discovery import STACSearchCatalog


class E84Sentinel2COGs(STACSearchCatalog):
    COLLECTION = "sentinel-s2-l2a-cogs"
    ENDPOINT = "https://earth-search.aws.element84.com/v0/"
