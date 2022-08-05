from abc import ABC, abstractmethod

from mapchete_eo.known_catalogs import CATALOGS


class Storage(ABC):
    """
    Class holding useful information for a specific data storage such
    as access keys or tokens and preferred settings for fsspec and rasterio.
    """

    def __init__(self, **kwargs):
        self.os_key = kwargs.get("os_key")
        self.os_key_id = kwargs.get("os_key_id")
        self.request_payer = kwargs.get("request_payer")

    @abstractmethod
    @property
    def fs_options(self) -> dict:
        pass

    @abstractmethod
    @property
    def rio_env_options(self) -> dict:
        pass


class Archive(ABC):
    """
    An archive combines a Catalog and a Storage.
    """

    catalog_name = None
    storage_kwargs = None

    def __init__(
        self,
        os_key: str = None,
        os_key_id: str = None,
        request_payer: str = None,
        start_time: str = None,
        end_time: str = None,
        bounds: tuple = None,
    ):
        # self.storage = self.STORAGE_CLS(
        #     os_key=os_key, os_key_id=os_key_id, request_payer=request_payer
        # )
        self.catalog = CATALOGS[self.catalog_name](
            start_time=start_time,
            end_time=end_time,
            bounds=bounds,
        )
