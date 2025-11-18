from functools import cached_property
from typing import Any, Dict, List, Literal, Optional, Generator, Union, Callable

from mapchete.bounds import Bounds
from mapchete.path import MPath
from mapchete.types import BoundsLike, CRSLike, MPathLike
from pydantic import BaseModel, ConfigDict, model_validator
from pystac import Item
from shapely.geometry.base import BaseGeometry
from shapely.errors import GEOSException

from mapchete_eo.exceptions import ItemGeometryError
from mapchete_eo.search.base import CollectionSearcher
from mapchete_eo.search import STACSearchCollection, STACStaticCollection
from mapchete_eo.settings import mapchete_eo_settings
from mapchete_eo.types import TimeRange


class Source(BaseModel):
    """All information required to consume EO products."""

    collection: str
    catalog_crs: Optional[CRSLike] = mapchete_eo_settings.default_catalog_crs
    query: Optional[str] = None
    area: Optional[Union[MPathLike, dict, type[BaseGeometry]]] = None
    bounds: Optional[BoundsLike] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def item_modifier_funcs(self) -> List[Callable]:
        return []

    @cached_property
    def catalog_type(self) -> Literal["search", "static"]:
        # TODO: stupid test but probably sufficient
        return "static" if self.collection.endswith(".json") else "search"

    def _spatial_subset(
        self,
        bounds: Optional[BoundsLike] = None,
        area: Optional[BaseGeometry] = None,
    ) -> Dict[str, Any]:
        """Combine bounds and area with bounds defined in Source if any."""
        if self.bounds is None:
            return {"bounds": bounds, "area": area}
        self_bounds = Bounds.from_inp(self.bounds)
        out = dict()
        if bounds is not None:
            bounds = Bounds.from_inp(bounds)
            if bounds.intersects(self_bounds):
                out["bounds"] = Bounds.from_inp(
                    bounds.geometry.intersection(self_bounds.geometry)
                )
        if area is not None:
            out["area"] = area.intersection(self_bounds.geometry)
        return out

    def search(
        self,
        time: Optional[Union[TimeRange, List[TimeRange]]] = None,
        bounds: Optional[BoundsLike] = None,
        area: Optional[BaseGeometry] = None,
        base_dir: Optional[MPathLike] = None,
    ) -> Generator[Item, None, None]:
        for item in self.get_catalog(base_dir=base_dir).search(
            time=time,
            query=self.query,
            search_kwargs=dict(query=self.query) if self.query else None,
            **self._spatial_subset(
                bounds=bounds,
                area=area,
            ),
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

    def get_catalog(self, base_dir: Optional[MPathLike] = None) -> CollectionSearcher:
        match self.catalog_type:
            case "search":
                return STACSearchCollection(self.collection)
            case "static":
                return STACStaticCollection(
                    collection=MPath(self.collection).absolute_path(base_dir=base_dir)
                )

    def eo_bands(self, base_dir: Optional[MPathLike] = None) -> List[str]:
        return self.get_catalog(base_dir=base_dir).eo_bands

    @model_validator(mode="before")
    def deprecate_max_cloud_cover(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if "max_cloud_cover" in values:
            raise DeprecationWarning(
                "'max_cloud_cover' will be deprecated soon. Please use 'eo:cloud_cover<=...' in the source 'query' field.",
            )
        elif "area" in values:  # pragma: no cover
            raise NotImplementedError("please use 'bounds' as spatial subset for now")
        return values
