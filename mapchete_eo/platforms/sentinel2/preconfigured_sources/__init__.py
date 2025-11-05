from typing import Literal, Dict, Any

# importing this is crucial so the mapping functions get registered before registry is accessed
from mapchete_eo.platforms.sentinel2.preconfigured_sources.item_mappers import (
    earthsearch_assets_paths_mapper,  # noqa: F401
    earthsearch_id_mapper,  # noqa: F401
    earthsearch_to_s2metadata,  # noqa: F401
    cdse_asset_names,  # noqa: F401
    cdse_s2metadata,  # noqa: F401
)
from mapchete_eo.platforms.sentinel2.preconfigured_sources.guessers import (
    guess_metadata_path_mapper,
    guess_s2metadata_from_item,
    guess_s2metadata_from_metadata_xml,
)


__all__ = [
    "guess_metadata_path_mapper",
    "guess_s2metadata_from_item",
    "guess_s2metadata_from_metadata_xml",
]

DataArchive = Literal["AWSCOG", "AWSJP2"]
KNOWN_SOURCES: Dict[str, Any] = {
    "EarthSearch": {
        "collection": "https://earth-search.aws.element84.com/v1/collections/sentinel-2-c1-l2a",
    },
    "EarthSearch_legacy": {
        "collection": "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a",
    },
    "CDSE": {
        "collection": "https://stac.dataspace.copernicus.eu/v1/collections/sentinel-2-l2a",
    },
}

DEPRECATED_ARCHIVES = {
    "S2AWS_COG": {
        "collection": "https://earth-search.aws.element84.com/v1/collections/sentinel-2-c1-l2a",
    },
    "S2AWS_JP2": {
        "collection": "https://stac.dataspace.copernicus.eu/v1/collections/sentinel-2-l2a",
        "data_archive": "AWSJP2",
    },
    "S2CDSE_AWSJP2": {
        "collection": "https://stac.dataspace.copernicus.eu/v1/collections/sentinel-2-l2a",
        "data_archive": "AWSJP2",
    },
    "S2CDSE_JP2": {
        "collection": "https://stac.dataspace.copernicus.eu/v1/collections/sentinel-2-l2a",
    },
}
MetadataArchive = Literal["roda"]
