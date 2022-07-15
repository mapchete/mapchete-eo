import os

import pystac
from mapchete.io import fs_from_path
from mapchete.io.vector import IndexedFeatures
from pystac.collection import Collection
from pystac.stac_io import DefaultStacIO

from mapchete_eo.io.convert import copy_asset


class FSSpecStacIO(DefaultStacIO):
    """Custom class which allows I/O operations on object storage."""

    def read_text(self, source: str, *args, **kwargs) -> str:
        fs = fs_from_path(source)
        with fs.open(source) as src:
            return src.read()

    def write_text(self, dest: str, txt: str, *args, **kwargs) -> None:
        fs = fs_from_path(dest)
        fs.mkdirs(os.path.dirname(dest), exist_ok=True)
        with fs.open(dest, "w", auto_mkdir=True) as dst:
            return dst.write(txt)


class Catalog:
    @property
    def items(self) -> IndexedFeatures:
        raise NotImplementedError("catalog class has not implemented this property")

    @property
    def eo_bands(self) -> list:
        raise NotImplementedError("catalog class has not implemented this property")

    def write_static_catalog(
        self,
        output_path: str,
        name: str = None,
        description: str = None,
        copy_assets: list = None,
    ):
        """Dump static version of current items."""
        if len(self.collections) > 1:
            raise ValueError(
                f"{len(self.collections)} collections found. Writing static STAC catalog is "
                "currently only possible with exactly one collection"
            )

        # create collection and copy metadata
        collection = self.client.get_collection(self.collections[0])
        new_collection = Collection(
            id=collection.id,
            extent=pystac.Extent(spatial=[], temporal=[]),
            description=collection.description,
            title=collection.title,
            stac_extensions=collection.stac_extensions,
            license=collection.license,
            keywords=collection.keywords,
            providers=collection.providers,
            summaries=collection.summaries,
            extra_fields=collection.extra_fields,
        )
        for item in self.items:
            if copy_assets:
                for asset in copy_assets:
                    item = copy_asset(
                        item, asset, os.path.join(output_path, collection.id, item.id)
                    )
            new_collection.add_item(item)
        new_collection.update_extent_from_items()

        # initialize catalog
        catalog_json = os.path.join(output_path, "catalog.json")
        catalog = pystac.Catalog(
            name or f"{self.client.id}",
            description or f"Subset of {self.client.description}",
            stac_extensions=self.client.stac_extensions,
            href=catalog_json,
        )

        catalog.add_child(new_collection)
        catalog.normalize_and_save(
            output_path, catalog_type=pystac.CatalogType.SELF_CONTAINED
        )

        return catalog_json
