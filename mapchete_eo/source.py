from typing import List, Literal, Optional, Generator, Union, Dict, Any, Callable

from mapchete.path import MPath
from mapchete.types import BoundsLike, CRSLike, MPathLike
from pydantic import BaseModel, ConfigDict
from pystac import Item
from shapely.geometry.base import BaseGeometry
from shapely.errors import GEOSException

from mapchete_eo.exceptions import ItemGeometryError
from mapchete_eo.search.base import CatalogSearcher
from mapchete_eo.search import STACSearchCatalog, STACStaticCatalog
from mapchete_eo.settings import mapchete_eo_settings
from mapchete_eo.types import TimeRange


class Source(BaseModel):
    """All information required to consume EO products."""

    stac_catalog: str
    collections: Optional[List[str]] = None
    catalog_crs: CRSLike = mapchete_eo_settings.default_catalog_crs
    catalog_type: Literal["search", "static"] = "search"

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def item_modifier_funcs(self) -> List[Callable]:
        return []

    def search(
        self,
        time: Union[TimeRange, List[TimeRange]],
        bounds: Optional[BoundsLike] = None,
        area: Optional[BaseGeometry] = None,
        search_kwargs: Optional[Dict[str, Any]] = None,
        base_dir: Optional[MPathLike] = None,
    ) -> Generator[Item, None, None]:
        for item in self.get_catalog(base_dir=base_dir).search(
            time=time, bounds=bounds, area=area, search_kwargs=search_kwargs
        ):
            yield self.apply_item_modifier_funcs(item)

    def apply_item_modifier_funcs(self, item: Item) -> Item:
        try:
            for modifier in self.item_modifier_funcs:
                item = modifier(item)
        except GEOSException as exc:
            raise ItemGeometryError(
                f"item {item.get_self_href()} geometry could not be resolved: {str(exc)}"
            )
        return item

    def get_catalog(self, base_dir: Optional[MPathLike] = None) -> CatalogSearcher:
        match self.catalog_type:
            case "search":
                return STACSearchCatalog(
                    endpoint=self.stac_catalog, collections=self.collections
                )
            case "static":
                return STACStaticCatalog(
                    baseurl=MPath(self.stac_catalog).absolute_path(base_dir=base_dir)
                )

    def eo_bands(self) -> List[str]:
        return self.get_catalog().eo_bands
