from typing import Optional, Dict, Any

from mapchete.path import MPath, MPathLike
from pydantic import BaseModel, model_validator


class StacSearchConfig(BaseModel):
    max_cloud_cover: float = 100.0
    query: Optional[str] = None
    catalog_chunk_threshold: int = 10_000
    catalog_chunk_zoom: int = 5
    catalog_pagesize: int = 100
    footprint_buffer: float = 0

    @model_validator(mode="before")
    def deprecate_max_cloud_cover(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if "max_cloud_cover" in values:  # pragma: no cover
            raise DeprecationWarning(
                "'max_cloud_cover' will be deprecated soon. Please use 'eo:cloud_cover<=...' in the source 'query' field.",
            )
        return values


class StacStaticConfig(BaseModel):
    @model_validator(mode="before")
    def deprecate_max_cloud_cover(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if "max_cloud_cover" in values:  # pragma: no cover
            raise DeprecationWarning(
                "'max_cloud_cover' will be deprecated soon. Please use 'eo:cloud_cover<=...' in the source 'query' field.",
            )
        return values


class UTMSearchConfig(BaseModel):
    @model_validator(mode="before")
    def deprecate_max_cloud_cover(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if "max_cloud_cover" in values:  # pragma: no cover
            raise DeprecationWarning(
                "'max_cloud_cover' will be deprecated soon. Please use 'eo:cloud_cover<=...' in the source 'query' field.",
            )
        return values

    sinergise_aws_collections: dict = dict(
        S2_L2A=dict(
            id="sentinel-s2-l2a",
            path=MPath(
                "https://sentinel-s2-l2a-stac.s3.amazonaws.com/sentinel-s2-l2a.json"
            ),
        ),
        S2_L1C=dict(
            id="sentinel-s2-l1c",
            path=MPath(
                "https://sentinel-s2-l1c-stac.s3.amazonaws.com/sentinel-s2-l1c.json"
            ),
        ),
        S1_GRD=dict(
            id="sentinel-s1-l1c",
            path=MPath(
                "https://sentinel-s1-l1c-stac.s3.amazonaws.com/sentinel-s1-l1c.json"
            ),
        ),
    )
    search_index: Optional[MPathLike] = None
