from abc import ABC
import logging
from typing import Any, Callable, Dict, Generator, List, Optional, Union

from mapchete.io.vector import IndexedFeatures
from mapchete.types import Bounds
from pystac import Item
from shapely.errors import GEOSException
from shapely.geometry.base import BaseGeometry

from mapchete_eo.exceptions import ItemGeometryError
from mapchete_eo.search.base import CatalogSearcher
from mapchete_eo.types import TimeRange

logger = logging.getLogger(__name__)


class Archive(ABC):
    """
    An archive combines a Catalog and a Storage.
    """

    time: Union[TimeRange, List[TimeRange]]
    area: BaseGeometry
    catalog: CatalogSearcher
    search_kwargs: Dict[str, Any]
    _items: Optional[IndexedFeatures] = None
    item_modifier_funcs: Optional[List[Callable[[Item], Item]]] = None

    def __init__(
        self,
        time: Union[TimeRange, List[TimeRange]],
        bounds: Optional[Bounds] = None,
        area: Optional[BaseGeometry] = None,
        search_kwargs: Optional[Dict[str, Any]] = None,
        catalog: Optional[CatalogSearcher] = None,
    ):
        if bounds is None and area is None:
            raise ValueError("either bounds or area have to be provided")
        elif area is None:
            area = Bounds.from_inp(bounds).geometry
        self.time = time
        self.area = area
        self.search_kwargs = search_kwargs or {}
        if catalog:
            self.catalog = catalog

    def get_catalog_config(self):
        return self.catalog.config_cls(**self.search_kwargs)

    def apply_item_modifier_funcs(self, item: Item) -> Item:
        try:
            for modifier in self.item_modifier_funcs or []:
                item = modifier(item)
        except GEOSException as exc:
            raise ItemGeometryError(
                f"item {item.get_self_href()} geometry could not be resolved: {str(exc)}"
            )
        return item

    def items(self) -> Generator[Item, None, None]:
        for item in self.catalog.search(
            time=self.time, area=self.area, search_kwargs=self.search_kwargs
        ):
            yield self.apply_item_modifier_funcs(item)
