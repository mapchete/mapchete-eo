import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Generator, List, Optional, Type, Union

from pydantic import BaseModel
from pystac import Item, Catalog, CatalogType, Extent
from mapchete.path import MPath, MPathLike
from mapchete.types import Bounds
from pystac.collection import Collection
from pystac.stac_io import DefaultStacIO
from pystac_client import Client
from pystac_client.stac_api_io import StacApiIO
from rasterio.profiles import Profile
from shapely.geometry.base import BaseGeometry

from mapchete_eo.io.assets import get_assets, get_metadata_assets
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


class CatalogSearcher(ABC):
    """
    This class serves as a bridge between an Archive and a catalog implementation.
    """

    eo_bands: List[str]
    id: str
    description: str
    stac_extensions: List[str]
    collections: List[str]
    config_cls: Type[BaseModel]

    @abstractmethod
    def search(
        self,
        time: Optional[Union[TimeRange, List[TimeRange]]] = None,
        bounds: Optional[Bounds] = None,
        area: Optional[BaseGeometry] = None,
        search_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Generator[Item, None, None]: ...


class StaticCatalogWriterMixin(CatalogSearcher):
    client: Client
    id: str
    description: str
    stac_extensions: List[str]

    @abstractmethod
    def get_collections(self) -> List[Collection]:  # pragma: no cover
        ...

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
            client = Client.from_file(catalog_json)
            # catalog = pystac.Catalog.from_file(catalog_json)
            existing_collections = list(client.get_collections())
        else:
            existing_collections = []
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
        for collection in self.get_collections():
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
                        output_path / collection.id / item.id,
                        resolution=assets_dst_resolution,
                        convert_profile=assets_convert_profile,
                        overwrite=overwrite,
                        ignore_if_exists=True,
                    )
                if copy_metadata:
                    item = get_metadata_assets(
                        item,
                        output_path / collection.id / item.id,
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

            for existing_collection in existing_collections:
                if existing_collection.id == collection.id:
                    logger.debug("try to find unregistered items in collection")
                    collection_root_path = MPath.from_inp(
                        existing_collection.get_self_href()
                    ).parent
                    for subpath in collection_root_path.ls():
                        if subpath.is_directory():
                            try:
                                item = Item.from_file(
                                    subpath / subpath.with_suffix(".json").name
                                )
                                if item.id not in item_ids:
                                    logger.debug(
                                        "add existing item with id %s", item.id
                                    )
                                    items.append(item)
                                    item_ids.add(item.id)
                            except FileNotFoundError:
                                pass
                    break
            # create collection and copy metadata
            logger.debug("create new collection")
            out_collection = Collection(
                id=collection.id,
                extent=Extent.from_items(items),
                description=collection.description,
                title=collection.title,
                stac_extensions=collection.stac_extensions,
                license=collection.license,
                keywords=collection.keywords,
                providers=collection.providers,
                summaries=collection.summaries,
                extra_fields=collection.extra_fields,
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
    cloud_cover_field: str = "eo:cloud_cover",
    max_cloud_cover: float = 100.0,
) -> Generator[Item, None, None]:
    """
    Only for cloudcover now, this can and should be adapted for filter field and value
    the field and value for the item filter would be defined in search.config.py corresponding configs
    and passed down to the individual search approaches via said config and this Function.
    """
    for item in items:
        if item.properties.get(cloud_cover_field, 0.0) <= max_cloud_cover:
            yield item
