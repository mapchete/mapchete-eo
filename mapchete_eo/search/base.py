from abc import ABC, abstractmethod
import json
import logging
import os
from typing import Union, List

from mapchete.io import fs_from_path
from mapchete.io.vector import IndexedFeatures
import pystac
from pystac.collection import Collection
from pystac.stac_io import DefaultStacIO
from pystac_client import Client
from pystac_client.stac_api_io import StacApiIO

from mapchete_eo.io.assets import get_assets

logger = logging.getLogger(__name__)


class FSSpecStacIO(StacApiIO):
    """Custom class which allows I/O operations on object storage."""

    def read_text(self, source: Union[str, os.PathLike], *args, **kwargs) -> str:
        fs = fs_from_path(source)
        with fs.open(source) as src:
            return src.read()

    def write_text(
        self, dest: Union[str, os.PathLike], txt: str, *args, **kwargs
    ) -> None:
        fs = fs_from_path(dest)
        fs.mkdirs(os.path.dirname(dest), exist_ok=True)
        with fs.open(dest, "w", auto_mkdir=True) as dst:
            return dst.write(txt)

    # TODO: investigate in pystac why this has to be a staticmethod
    @staticmethod
    def save_json(
        dest: Union[str, os.PathLike], json_dict: dict, *args, **kwargs
    ) -> None:
        json_txt = json.dumps(json_dict)
        fs = fs_from_path(dest)
        fs.mkdirs(os.path.dirname(dest), exist_ok=True)
        with fs.open(dest, "w", auto_mkdir=True) as dst:
            return dst.write(json_txt)

    def conforms_to(self, *args):
        # required otherwise generating static catalog subset from static
        # catalog won't work
        return False


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
        output_path: str,
        name: Union[str, None] = None,
        description: Union[str, None] = None,
        assets: List[str] = [],
        assets_dst_resolution: Union[int, None] = None,
        overwrite: bool = False,
        stac_io: DefaultStacIO = FSSpecStacIO(),
    ):
        """Dump static version of current items."""

        # initialize catalog
        catalog_json = os.path.join(output_path, "catalog.json")
        catalog = pystac.Catalog(
            name or f"{self.client.id}",
            description or f"Static subset of {self.client.description}",
            stac_extensions=self.client.stac_extensions,
            href=catalog_json,
            catalog_type=pystac.CatalogType.SELF_CONTAINED,
        )
        for collection in self.get_collections():

            # collect all items and download assets if required
            items: List[pystac.Item] = []
            for item in self.items:
                logger.debug("found item %s", item)
                item = item.clone()
                if assets:
                    logger.debug("get assets %s", assets)
                    item = get_assets(
                        item,
                        assets,
                        os.path.join(output_path, collection.id, item.id),
                        resolution=assets_dst_resolution,
                        overwrite=overwrite,
                        ignore_if_exists=True,
                    )
                # this has to be set to None, otherwise pystac will mess up the asset paths
                # after normalizing
                item.set_self_href(None)
                items.append(item)

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
        catalog.normalize_hrefs(output_path)
        catalog.make_all_asset_hrefs_relative()
        catalog.save(dest_href=output_path, stac_io=stac_io)

        return catalog_json
