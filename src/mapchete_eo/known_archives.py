# from mapchete_eo.archives.base import Archive
from mapchete_eo.known_catalogs import E84Sentinel2COGs


class Archive:

    CATALOG_CLS = None
    STORAGE_CLS = None

    def __init__(
        self,
        os_key: str = None,
        os_key_id: str = None,
        request_payer: str = None,
        start_time: str = None,
        end_time: str = None,
        bounds: tuple = None,
    ):
        self.storage = self.STORAGE_CLS(
            os_key=os_key, os_key_id=os_key_id, request_payer=request_payer
        )
        self.catalog = self.CATALOG_CLS(
            start_time=start_time,
            end_time=end_time,
            bounds=bounds,
        )


class Storage:
    def __init__(self, **kwargs):
        self.os_key = kwargs.get("os_key")
        self.os_key_id = kwargs.get("os_key_id")
        self.request_payer = kwargs.get("request_payer")


class S2AWSL2ACOG(Storage):
    BASEURL = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/"
    pass


class S2AWSCOGArchive(Archive):

    CATALOG_CLS = E84Sentinel2COGs
    STORAGE_CLS = S2AWSL2ACOG
