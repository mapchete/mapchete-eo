from functools import cached_property
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Generator, List, Optional, Set, Type, Union

from pygeofilter.parsers.ecql import parse as parse_ecql
from pygeofilter.backends.native.evaluate import NativeEvaluator
from pydantic import BaseModel
from mapchete.path import MPath, MPathLike
from mapchete.types import Bounds
from pystac import Catalog, Item, CatalogType, Extent
from pystac.collection import Collection
from pystac.stac_io import DefaultStacIO
from pystac_client import CollectionClient
from pystac_client.stac_api_io import StacApiIO
from rasterio.profiles import Profile
from shapely.geometry.base import BaseGeometry

from mapchete_eo.io.assets import get_assets, get_metadata_assets
from mapchete_eo.product import blacklist_products
from mapchete_eo.settings import mapchete_eo_settings
from mapchete_eo.types import TimeRange

logger = logging.getLogger(__name__)


class FSSpecStacIO(StacApiIO):
    """Custom class which allows I/O operations on object storage."""

    def read_text(self, source: MPathLike, *args, **kwargs) -> str:
        return MPath.from_inp(source).read_text()

    def write_text(self, dest: MPathLike, txt: str, *args, **kwargs) -> None:
        path = MPath.from_inp(dest)
        if not path.parent.exists():
            path.parent.makedirs(exist_ok=True)
        with path.open("w") as dst:
            return dst.write(txt)

    # TODO: investigate in pystac why this has to be a staticmethod
    @staticmethod
    def save_json(dest: MPathLike, json_dict: dict, *args, **kwargs) -> None:
        path = MPath.from_inp(dest)
        if not path.parent.exists():
            path.parent.makedirs(exist_ok=True)
        with path.open("w") as dst:
            return dst.write(json.dumps(json_dict, indent=2))


class CollectionSearcher(ABC):
    """
    This class serves as a bridge between an Archive and a catalog implementation.
    """

    config_cls: Type[BaseModel]
    collection: str
    stac_item_modifiers: Optional[List[Callable[[Item], Item]]] = None
    blacklist: Set[str] = (
        blacklist_products(mapchete_eo_settings.blacklist)
        if mapchete_eo_settings.blacklist
        else set()
    )

    def __init__(
        self,
        collection: str,
        stac_item_modifiers: Optional[List[Callable[[Item], Item]]] = None,
    ):
        self.collection = collection
        self.stac_item_modifiers = stac_item_modifiers

    @abstractmethod
    @cached_property
    def client(self) -> CollectionClient: ...

    @abstractmethod
    @cached_property
    def eo_bands(self) -> List[str]: ...

    @property
    def config(self) -> BaseModel:
        return self.config_cls()

    @cached_property
    def id(self) -> str:
        return self.client.id

    @cached_property
    def description(self) -> str:
        return self.client.description

    @cached_property
    def stac_extensions(self) -> List[str]:
        return self.client.stac_extensions

    @abstractmethod
    def search(
        self,
        time: Optional[Union[TimeRange, List[TimeRange]]] = None,
        bounds: Optional[Bounds] = None,
        area: Optional[BaseGeometry] = None,
        query: Optional[str] = None,
        search_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Generator[Item, None, None]: ...


class StaticCollectionWriterMixin(CollectionSearcher):
    # client: Client
    # id: str
    # description: str
    # stac_extensions: List[str]

    def write_static_catalog(
        self,
        output_path: MPathLike,
        bounds: Optional[Bounds] = None,
        area: Optional[BaseGeometry] = None,
        time: Optional[TimeRange] = None,
        search_kwargs: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        assets: Optional[List[str]] = None,
        assets_dst_resolution: Union[None, float, int] = None,
        assets_convert_profile: Optional[Profile] = None,
        copy_metadata: bool = False,
        metadata_parser_classes: Optional[tuple] = None,
        overwrite: bool = False,
        stac_io: DefaultStacIO = FSSpecStacIO(),
        progress_callback: Optional[Callable] = None,
    ) -> MPath:
        """Dump static version of current items."""
        output_path = MPath.from_inp(output_path)
        assets = assets or []
        # initialize catalog
        catalog_json = output_path / "catalog.json"
        if catalog_json.exists():
            logger.debug("open existing catalog %s", str(catalog_json))
            catalog = Catalog.from_file(catalog_json)
            # client = Client.from_file(catalog_json)
            # existing_collection = client.get_collection(self.id)
        else:
            # existing_collections = []
            catalog = Catalog(
                name or f"{self.id}",
                description or f"Static subset of {self.description}",
                stac_extensions=self.stac_extensions,
                href=str(catalog_json),
                catalog_type=CatalogType.SELF_CONTAINED,
            )
        src_items = list(
            self.search(
                time=time, bounds=bounds, area=area, search_kwargs=search_kwargs
            )
        )
        # collect all items and download assets if required
        items: List[Item] = []
        item_ids = set()
        for n, item in enumerate(src_items, 1):
            logger.debug("found item %s", item)
            item = item.clone()
            if assets:
                logger.debug("get assets %s", assets)
                item = get_assets(
                    item,
                    assets,
                    output_path / self.id / item.id,
                    resolution=assets_dst_resolution,
                    convert_profile=assets_convert_profile,
                    overwrite=overwrite,
                    ignore_if_exists=True,
                )
            if copy_metadata:
                item = get_metadata_assets(
                    item,
                    output_path / self.id / item.id,
                    metadata_parser_classes=metadata_parser_classes,
                    resolution=assets_dst_resolution,
                    convert_profile=assets_convert_profile,
                    overwrite=overwrite,
                )
            # this has to be set to None, otherwise pystac will mess up the asset paths
            # after normalizing
            item.set_self_href(None)

            items.append(item)
            item_ids.add(item.id)

            if progress_callback:
                progress_callback(n=n, total=len(src_items))

            # for existing_collection in existing_collections:
            #     if existing_collection.id == collection.id:
            #         logger.debug("try to find unregistered items in collection")
            #         collection_root_path = MPath.from_inp(
            #             existing_collection.get_self_href()
            #         ).parent
            #         for subpath in collection_root_path.ls():
            #             if subpath.is_directory():
            #                 try:
            #                     item = Item.from_file(
            #                         subpath / subpath.with_suffix(".json").name
            #                     )
            #                     if item.id not in item_ids:
            #                         logger.debug(
            #                             "add existing item with id %s", item.id
            #                         )
            #                         items.append(item)
            #                         item_ids.add(item.id)
            #                 except FileNotFoundError:
            #                     pass
            #         break
            # create collection and copy metadata
            logger.debug("create new collection")
            out_collection = Collection(
                id=self.id,
                extent=Extent.from_items(items),
                description=self.description,
                title=self.client.title,
                stac_extensions=self.stac_extensions,
                license=self.client.license,
                keywords=self.client.keywords,
                providers=self.client.providers,
                summaries=self.client.summaries,
                extra_fields=self.client.extra_fields,
                catalog_type=CatalogType.SELF_CONTAINED,
            )

            # finally, add all items to collection
            for item in items:
                out_collection.add_item(item)

            out_collection.update_extent_from_items()

            catalog.add_child(out_collection)

        logger.debug("write catalog to %s", output_path)
        catalog.normalize_hrefs(str(output_path))
        catalog.make_all_asset_hrefs_relative()
        catalog.save(dest_href=str(output_path), stac_io=stac_io)

        return catalog_json


def filter_items(
    items: Generator[Item, None, None],
    query: Optional[str] = None,
) -> Generator[Item, None, None]:
    """
    Only for cloudcover now, this can and should be adapted for filter field and value
    the field and value for the item filter would be defined in search.config.py corresponding configs
    and passed down to the individual search approaches via said config and this Function.
    """
    if query:
        ast = parse_ecql(query)
        evaluator = NativeEvaluator(use_getattr=False)
        filter_func = evaluator.evaluate(ast)
        for item in items:
            # pystac items store metadata in 'properties'
            if filter_func(item.properties):
                yield item
    else:
        yield from items
