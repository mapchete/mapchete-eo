from typing import Literal, Dict, Any

from pystac import Item

from mapchete_eo.platforms.sentinel2.mapper_registry import (
    maps_item_id,
    maps_asset_paths,
    creates_s2metadata,
)
from mapchete_eo.platforms.sentinel2.metadata_parser import S2Metadata


DataArchive = Literal["AWSCOG", "AWSJP2"]
KNOWN_SOURCES: Dict[str, Any] = {
    "EarthSearch": {
        "stac_catalog": "https://earth-search.aws.element84.com/v1/",
        "collections": ["sentinel-2-l2a"],
        "data_archive": "AWSCOG",
    },
    "CDSE": {
        "stac_catalog": "https://stac.dataspace.copernicus.eu/v1",
        "collections": ["sentinel-2-l2a"],
    },
}
MetadataArchive = Literal["roda"]


# mapper functions decorated with metadata to have driver decide which one to apply when #
##########################################################################################


@maps_item_id(from_catalogs=["EarthSearch"])
def earthsearch_id_mapper(item: Item) -> Item:
    return item


@maps_asset_paths(from_catalogs=["EarthSearch"], to_data_archives=["AWSCOG"])
def earthsearch_path_mapper(item: Item) -> Item:
    return item


@creates_s2metadata(from_catalogs=["EarthSearch"], to_metadata_archives=["roda"])
def earthsearch_to_s2metadata(item: Item) -> S2Metadata:
    return S2Metadata.from_stac_item(item)


@maps_item_id(from_catalogs=["CDSE"])
def plain_id_mapper(item: Item) -> Item:
    return item
