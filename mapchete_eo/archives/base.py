from abc import ABC
from typing import Type, Union

from mapchete.types import Bounds
from shapely.geometry.base import BaseGeometry

from mapchete_eo.search.base import Catalog
from mapchete_eo.types import DateTimeLike


class Archive(ABC):
    """
    An archive combines a Catalog and a Storage.
    """

    catalog_cls: Type[Catalog]
    collection_name: str

    def __init__(
        self,
        start_time: Union[DateTimeLike, None] = None,
        end_time: Union[DateTimeLike, None] = None,
        bounds: Union[Bounds, None] = None,
        area: Union[BaseGeometry, None] = None,
        **kwargs
    ):
        self.catalog = self.catalog_cls(
            collections=[self.collection_name],
            start_time=start_time,
            end_time=end_time,
            bounds=bounds,
            area=area,
            **kwargs
        )


class StaticArchive(Archive):
    def __init__(self, catalog=None, **kwargs):
        self.catalog = catalog
