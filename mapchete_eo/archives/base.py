from abc import ABC, abstractmethod
from typing import Any

from mapchete_eo.search.base import Catalog


class Archive(ABC):
    """
    An archive combines a Catalog and a Storage.
    """

    catalog_cls: type[Catalog]
    collection: str

    def __init__(self, start_time=None, end_time=None, bounds=None):
        self.catalog = self.catalog_cls(
            collections=[self.collection],
            start_time=start_time,
            end_time=end_time,
            bounds=bounds,
        )
