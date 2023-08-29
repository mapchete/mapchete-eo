import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Callable, List, Union

import pystac
from mapchete.io.vector import IndexedFeatures
from mapchete.path import MPath
from pystac.collection import Collection
from pystac.stac_io import DefaultStacIO
from pystac_client import Client
from pystac_client.stac_api_io import StacApiIO
from rasterio.profiles import Profile

from mapchete_eo.io.assets import copy_metadata_assets, get_assets

logger = logging.getLogger(__name__)


class FSSpecStacIO(StacApiIO):
    """Custom class which allows I/O operations on object storage."""

    def read_text(self, source: Union[str, os.PathLike, MPath], *args, **kwargs) -> str:
        path = MPath.from_inp(source)
        return path.read_text()

    def write_text(
        self, dest: Union[str, os.PathLike, MPath], txt: str, *args, **kwargs
    ) -> None:
        path = MPath.from_inp(dest)
        path.parent.makedirs(exist_ok=True)
        with path.open("w") as dst:
            return dst.write(txt)

    # TODO: investigate in pystac why this has to be a staticmethod
    @staticmethod
    def save_json(
        dest: Union[str, os.PathLike, MPath], json_dict: dict, *args, **kwargs
    ) -> None:
        path = MPath.from_inp(dest)
        path.parent.makedirs(exist_ok=True)
        with path.open("w") as dst:
            return dst.write(json.dumps(json_dict))


class Catalog(ABC):
    client: Client

    @property
    @abstractmethod
    def items(self) -> IndexedFeatures:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def eo_bands(self) -> list:  # pragma: no cover
        ...

    @abstractmethod
    def get_collections(self) -> List[Collection]:  # pragma: no cover
        ...

    def write_static_catalog(
        self,
        output_path: Union[MPath, str],
        name: Union[str, None] = None,
        description: Union[str, None] = None,
        assets: List[str] = [],
        assets_dst_resolution: Union[None, float, int] = None,
        assets_convert_profile: Union[Profile, None] = None,
        copy_metadata: bool = False,
        metadata_parser_classes: Union[tuple, None] = None,
        overwrite: bool = False,
        stac_io: DefaultStacIO = FSSpecStacIO(),
        progress_callback: Union[Callable, None] = None,
    ) -> MPath:
        """Dump static version of current items."""
        output_path = MPath.from_inp(output_path)

        # initialize catalog
        catalog_json = output_path / "catalog.json"
        catalog = pystac.Catalog(
            name or f"{self.client.id}",
            description or f"Static subset of {self.client.description}",
            stac_extensions=self.client.stac_extensions,
            href=str(catalog_json),
            catalog_type=pystac.CatalogType.SELF_CONTAINED,
        )
        for collection in self.get_collections():
            # collect all items and download assets if required
            items: List[pystac.Item] = []
            for n, item in enumerate(self.items, 1):
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
                    item = copy_metadata_assets(
                        item,
                        output_path / collection.id / item.id,
                        metadata_parser_classes=metadata_parser_classes,
                        overwrite=overwrite,
                    )
                # this has to be set to None, otherwise pystac will mess up the asset paths
                # after normalizing
                item.set_self_href(None)

                items.append(item)

                if progress_callback:
                    progress_callback(n=n, total=len(self.items))

            # create collection and copy metadata
            new_collection = Collection(
                id=collection.id,
                extent=pystac.Extent.from_items(items),
                description=collection.description,
                title=collection.title,
                stac_extensions=collection.stac_extensions,
                license=collection.license,
                keywords=collection.keywords,
                providers=collection.providers,
                summaries=collection.summaries,
                extra_fields=collection.extra_fields,
                catalog_type=pystac.CatalogType.SELF_CONTAINED,
            )

            # finally, add all items to collection
            for item in items:
                new_collection.add_item(item)

            catalog.add_child(new_collection)

        logger.debug("write catalog to %s", output_path)
        catalog.normalize_hrefs(str(output_path))
        catalog.make_all_asset_hrefs_relative()
        catalog.save(dest_href=str(output_path), stac_io=stac_io)

        return catalog_json
