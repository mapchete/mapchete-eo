from typing import List, Literal, Optional, Generator, Union, Callable, Dict, Any

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

from mapchete_eo.source_config import KNOWN_SOURCES


class Source(BaseModel):
    """All information required to consume EO products."""

    stac_catalog: str
    collections: Optional[List[str]] = None
    catalog_crs: CRSLike = mapchete_eo_settings.default_catalog_crs
    catalog_type: Literal["search", "static"] = "search"
    query: Optional[List[str]] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="before")
    def determine_data_source(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Handles short names of sources."""
        if isinstance(values, str):
            values = dict(stac_catalog=values)
        stac_catalog = values.get("stac_catalog", None)
        if stac_catalog in KNOWN_SOURCES:
            values.update(KNOWN_SOURCES[stac_catalog])
        else:
            # TODO: make sure catalog then is either a path or an URL
            pass
        return values

    @property
    def item_modifier_funcs(self) -> List[Callable]:
        return []

    def search(
        self,
        time: Optional[Union[TimeRange, List[TimeRange]]] = None,
        bounds: Optional[BoundsLike] = None,
        area: Optional[BaseGeometry] = None,
        base_dir: Optional[MPathLike] = None,
    ) -> Generator[Item, None, None]:
        """
        TODO: search needs to handle multiple collections and make (mapchete) EO Cubes
        """
        for item in self.get_catalog(base_dir=base_dir).search(
            time=time,
            bounds=bounds,
            area=area,
            search_kwargs=dict(collections=self.collections, query=self.query)
            if self.query
            else None,
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

    def eo_bands(self, base_dir: Optional[MPathLike] = None) -> List[str]:
        return self.get_catalog(base_dir=base_dir).eo_bands
