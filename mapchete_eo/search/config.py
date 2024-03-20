from typing import Union

from mapchete.path import MPath
from pydantic import BaseModel


class StacSearchConfig(BaseModel):
    max_cloud_percent: float = 100.0
    catalog_chunk_threshold: int = 10_000
    catalog_chunk_zoom: int = 5
    catalog_pagesize: int = 500


class UTMSearchConfig:
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
    mgrs_s2_grid: MPath = MPath(
        "/home/suprd/S2_Tiling_MGRS_Grid_S2A_OPER_GIP_TILPAR_MPC_B00.fgb"
        # "s3://eox-data/S2_Tiling_MGRS_Grid_S2A_OPER_GIP_TILPAR_MPC_B00.fgb"
    )
    utm_allowed_granules: Union[str, list] = "all"
