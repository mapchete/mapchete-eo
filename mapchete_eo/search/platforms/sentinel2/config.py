from pydantic import Field

from typing import List

from mapchete_eo.search.config import StacSearchConfig, UTMSearchConfig


ALLOWED_SENTINEL2_QUERIES_LIST: List[str] = ["eo:cloud_cover"]


class Sentinel2STACSearchQueryablesConfig(StacSearchConfig):
    max_cloud_cover: float = Field(100.0, serialization_alias="eo:cloud_cover")


class Sentinel2UTMSearchQueryablesConfig(UTMSearchConfig):
    max_cloud_cover: float = Field(100.0, serialization_alias="eo:cloud_cover")
