from pydantic import BaseModel


class StacSearchConfig(BaseModel):
    max_cloud_percent: float = 100.0
    catalog_chunk_threshold: int = 10_000
    catalog_chunk_zoom: int = 5
    catalog_pagesize: int = 500
