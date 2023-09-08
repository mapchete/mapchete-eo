from abc import ABC
from typing import Type

from mapchete_eo.search.base import Catalog


class Archive(ABC):
    """
    An archive combines a Catalog and a Storage.
    """

    catalog_cls: Type[Catalog]
    collection_name: str

    def __init__(self, start_time=None, end_time=None, bounds=None, **kwargs):
        self.catalog = self.catalog_cls(
            collections=[self.collection_name],
            start_time=start_time,
            end_time=end_time,
            bounds=bounds,
            **kwargs
        )


class StaticArchive(Archive):
    def __init__(self, catalog=None, **kwargs):
        self.catalog = catalog
