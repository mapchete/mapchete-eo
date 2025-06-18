from typing import Optional

from mapchete.path import MPath, MPathLike
from pydantic import BaseModel


class StacSearchConfig(BaseModel):
    max_cloud_cover: float = 100.0
    catalog_chunk_threshold: int = 10_000
    catalog_chunk_zoom: int = 5
    catalog_pagesize: int = 100
    footprint_buffer: float = 0


class StacStaticConfig(BaseModel):
    max_cloud_cover: float = 100.0


class UTMSearchConfig(BaseModel):
    max_cloud_cover: float = 100.0

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
