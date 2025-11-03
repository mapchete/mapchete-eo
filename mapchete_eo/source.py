from typing import Any, Dict, List, Literal, Optional, Generator, Union, Callable

from mapchete.path import MPath
from mapchete.types import BoundsLike, CRSLike, MPathLike
from pydantic import BaseModel, ConfigDict, model_validator
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

    collection: str
    catalog_crs: CRSLike = mapchete_eo_settings.default_catalog_crs
    catalog_type: Literal["search", "static"] = "search"
    query: Optional[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def item_modifier_funcs(self) -> List[Callable]:
        return []

    def search(
        self,
        time: Union[TimeRange, List[TimeRange]],
        bounds: Optional[BoundsLike] = None,
        area: Optional[BaseGeometry] = None,
        base_dir: Optional[MPathLike] = None,
    ) -> Generator[Item, None, None]:
        for item in self.get_catalog(base_dir=base_dir).search(
            time=time,
            bounds=bounds,
            area=area,
            query=self.query,
            search_kwargs=dict(query=self.query) if self.query else None,
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
                return STACSearchCatalog.from_collection_url(self.collection)
            case "static":
                return STACStaticCatalog(
                    baseurl=MPath(self.collection).absolute_path(base_dir=base_dir)
                )

    def eo_bands(self, base_dir: Optional[MPathLike] = None) -> List[str]:
        return self.get_catalog(base_dir=base_dir).eo_bands

    @model_validator(mode="before")
    def deprecate_max_cloud_cover(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if "max_cloud_cover" in values:
            raise DeprecationWarning(
                "'max_cloud_cover' will be deprecated soon. Please use 'eo:cloud_cover<=...' in the source 'query' field.",
            )
        return values
