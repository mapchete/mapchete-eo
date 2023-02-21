from abc import ABC
from typing import Type

from mapchete_eo.search.base import Catalog


class Archive(ABC):
    """
    An archive combines a Catalog and a Storage.
    """

    catalog_cls: Type[Catalog]
    collection: str

    def __init__(self, start_time=None, end_time=None, bounds=None):
        self.catalog = self.catalog_cls(
            collections=[self.collection],
            start_time=start_time,
            end_time=end_time,
            bounds=bounds,
        )
