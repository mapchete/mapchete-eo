from abc import ABC
from typing import List, Optional, Type, Union

from mapchete.types import Bounds
from shapely.geometry.base import BaseGeometry

from mapchete_eo.search.base import Catalog
from mapchete_eo.types import TimeRange


class Archive(ABC):
    """
    An archive combines a Catalog and a Storage.
    """

    catalog_cls: Type[Catalog]
    collection_name: str

    def __init__(
        self,
        time: Union[TimeRange, List[TimeRange]],
        bounds: Optional[Bounds] = None,
        area: Optional[BaseGeometry] = None,
        **kwargs
    ):
        self.catalog = self.catalog_cls(
            collections=[self.collection_name],
            time=time,
            bounds=bounds,
            area=area,
            **kwargs
        )


class StaticArchive(Archive):
    def __init__(self, catalog=None, **kwargs):
        self.catalog = catalog
